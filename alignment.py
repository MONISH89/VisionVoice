import time
import math
import logging
try:
    import cv2
except ImportError:
    cv2 = None

try:
    import numpy as np
except ImportError:
    np = None

import config

logger = logging.getLogger("VisionVoice.Alignment")

class PageAlignmentAnalyzer:
    """
    Real-time Page Alignment and Motion Stability Analyzer for VisionVoice.
    Continuously monitors camera frames headlessly to check whether a physical book page
    is suitably positioned, centered, upright, and steady within the scanning frame.

    ALIGNMENT PIPELINE:
      ALIGNING_PAGE
          ↓
      camera frame
          ↓
      page detection (contour analysis)
          ↓
      alignment assessment (area, center offsets, tilt angle)
          ↓
      stable & aligned for N consecutive frames (STABILITY_FRAMES_REQUIRED)
          ↓
      PAGE ALIGNED ("Page aligned.")
          ↓
      automatic capture
    """

    def __init__(self, required_stable_frames=config.STABILITY_FRAMES_REQUIRED):
        self.required_stable_frames = required_stable_frames
        self.last_frame_gray = None
        self.stable_counter = 0
        self.last_guidance_time = 0.0
        self.last_guidance_msg = ""

    def reset(self):
        """Resets stability counter state and debouncing timers."""
        self.last_frame_gray = None
        self.stable_counter = 0
        self.last_guidance_time = 0.0
        self.last_guidance_msg = ""

    def analyze_frame(self, frame):
        """
        Analyzes a single video frame for page alignment and motion stability.

        Args:
            frame (np.ndarray): Video frame captured from camera.

        Returns:
            dict containing:
                - 'is_aligned': bool (True if page is correctly positioned, sized, and oriented)
                - 'is_stable': bool (True if no excessive motion detected between frames)
                - 'ready_for_capture': bool (True if aligned and stable for N consecutive frames)
                - 'guidance': str (spoken directional instruction or "")
                - 'stability_counter': int (current consecutive stable frames count)
                - 'annotated_frame': np.ndarray or None (debug visual frame without GUI dependency)
        """
        if frame is None or cv2 is None or np is None:
            guidance = self._get_debounced_guidance("Place the book under the camera.")
            return self._build_result(False, False, False, guidance, 0, None)

        h, w = frame.shape[:2]
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        annotated = frame.copy() if getattr(config, "SHOW_DEV_PREVIEW", False) else None

        # 1. Target Scanning Frame (ROI Box)
        target_x1 = int(w * config.ROI_MARGIN_X)
        target_y1 = int(h * config.ROI_MARGIN_Y)
        target_x2 = int(w * (1.0 - config.ROI_MARGIN_X))
        target_y2 = int(h * (1.0 - config.ROI_MARGIN_Y))
        target_center_x = (target_x1 + target_x2) / 2.0
        target_center_y = (target_y1 + target_y2) / 2.0

        if annotated is not None:
            cv2.rectangle(annotated, (target_x1, target_y1), (target_x2, target_y2), (0, 255, 0), 2)

        # 2. Motion Stability Check
        is_stable = False
        if self.last_frame_gray is not None and self.last_frame_gray.shape == gray.shape:
            frame_diff = cv2.absdiff(gray, self.last_frame_gray)
            mean_diff = float(np.mean(frame_diff))
            is_stable = mean_diff < config.MOTION_PIXEL_THRESHOLD
        self.last_frame_gray = gray.copy()

        # 3. Detect Largest Quadrilateral (Page Candidate)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 11, 2)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        best_contour = None
        max_area = 0
        frame_area = float(w * h)

        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > max_area and area > (frame_area * 0.03):
                max_area = area
                best_contour = cnt

        if best_contour is None:
            # Fallback to Otsu thresholding
            _, otsu = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            contours, _ = cv2.findContours(otsu, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area > max_area and area > (frame_area * 0.03):
                    max_area = area
                    best_contour = cnt

        if best_contour is None:
            self.stable_counter = 0
            guidance = self._get_debounced_guidance("Place the book under the camera.")
            return self._build_result(False, is_stable, False, guidance, 0, annotated)

        # 4. Evaluate Bounding Geometry and Alignment
        rect = cv2.minAreaRect(best_contour)
        box_center, (box_w, box_h), angle = rect

        if annotated is not None:
            box_points = cv2.boxPoints(rect)
            box_pts = np.asarray(box_points, dtype=np.int32)
            cv2.drawContours(annotated, [box_pts], 0, (255, 0, 0), 2)

        # Normalize rotation angle
        if box_w < box_h:
            angle = angle + 90.0
        if angle > 45:
            angle -= 90
        elif angle < -45:
            angle += 90

        # Calculate Center Offsets & Area Ratio
        offset_x = (box_center[0] - target_center_x) / float(w)
        offset_y = (box_center[1] - target_center_y) / float(h)
        area_ratio = max_area / frame_area

        guidance = ""
        is_aligned = True

        # Check alignment criteria and determine directional guidance
        if area_ratio < config.ALIGNMENT_MIN_AREA_RATIO:
            is_aligned = False
            guidance = "Move the page closer."
        elif area_ratio > config.ALIGNMENT_MAX_AREA_RATIO:
            is_aligned = False
            guidance = "Move the page further away."
        elif offset_x > config.ALIGNMENT_CENTER_TOLERANCE_X:
            is_aligned = False
            guidance = "Move the page left."
        elif offset_x < -config.ALIGNMENT_CENTER_TOLERANCE_X:
            is_aligned = False
            guidance = "Move the page right."
        elif offset_y > config.ALIGNMENT_CENTER_TOLERANCE_Y:
            is_aligned = False
            guidance = "Move the page up."
        elif offset_y < -config.ALIGNMENT_CENTER_TOLERANCE_Y:
            is_aligned = False
            guidance = "Move the page down."
        elif abs(angle) > config.ALIGNMENT_MAX_TILT_ANGLE:
            is_aligned = False
            guidance = "Straighten the page."

        # 5. Stability Counter: Requires N consecutive stable and aligned frames
        if is_aligned and is_stable:
            self.stable_counter += 1
        elif not is_aligned:
            # Strictly reset on misalignment to ensure N consecutive frames
            self.stable_counter = 0
        else:
            # Aligned but motion detected: decrement counter
            self.stable_counter = max(0, self.stable_counter - 1)

        ready_for_capture = (self.stable_counter >= self.required_stable_frames)

        # 6. Spoken Directional Guidance Generation
        debounced_guidance = ""
        if not is_aligned and guidance:
            debounced_guidance = self._get_debounced_guidance(guidance)
        elif is_aligned and not is_stable:
            debounced_guidance = self._get_debounced_guidance("Hold the book steady.")

        return self._build_result(
            is_aligned=is_aligned,
            is_stable=is_stable,
            ready_for_capture=ready_for_capture,
            guidance=debounced_guidance,
            stability_counter=self.stable_counter,
            annotated_frame=annotated
        )

    def _get_debounced_guidance(self, msg):
        """Prevents voice guidance spamming by applying a cooldown period."""
        now = time.time()
        if (now - self.last_guidance_time) >= config.GUIDANCE_COOLDOWN_SEC or msg != self.last_guidance_msg:
            self.last_guidance_time = now
            self.last_guidance_msg = msg
            return msg
        return ""

    def _build_result(self, is_aligned, is_stable, ready_for_capture, guidance, stability_counter, annotated_frame):
        return {
            "is_aligned": is_aligned,
            "is_stable": is_stable,
            "ready_for_capture": ready_for_capture,
            "guidance": guidance,
            "stability_counter": stability_counter,
            "annotated_frame": annotated_frame
        }
