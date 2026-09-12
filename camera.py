import time
import threading
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

logger = logging.getLogger("VisionVoice.Camera")

class CameraManager:
    """
    Headless Camera Manager and Frame Acquisition Pipeline for VisionVoice.
    Provides clean hardware abstraction:
      - initialize()
      - capture_frame()
      - capture_page()
      - release()

    Operates completely headlessly on Raspberry Pi (Picamera2 / OpenCV VideoCapture).
    No GUI windows, cv2.imshow, or display dependencies.
    Camera failures produce explicit error states instead of infinite loops.
    """

    def __init__(self, camera_index=config.CAMERA_INDEX):
        self.camera_index = camera_index
        self.is_picam2 = False
        self.picam2 = None
        self.cap = None
        self.is_initialized = False
        self.has_error = False
        self.consecutive_errors = 0
        self.max_consecutive_errors = 10
        self.running = False
        self.lock = threading.Lock()
        self.current_frame = None
        self.thread = None

        self.initialize()

    def initialize(self):
        """
        Initializes the camera hardware interface (Picamera2 first, then OpenCV VideoCapture).
        Starts the background frame acquisition thread.
        Returns:
            bool: True if camera initialized successfully, False on failure.
        """
        if self.is_initialized and self.running:
            return True

        logger.info("Initializing headless camera subsystem...")
        self.has_error = False
        self.consecutive_errors = 0

        # 1. Attempt Picamera2 initialization (Raspberry Pi Camera Module 3)
        try:
            from picamera2 import Picamera2  # type: ignore
            self.picam2 = Picamera2()
            preview_config = self.picam2.create_preview_configuration(
                main={"size": config.CAPTURE_RESOLUTION, "format": "RGB888"},
                lores={"size": config.PREVIEW_RESOLUTION, "format": "YUV420"}
            )
            self.picam2.configure(preview_config)
            self.picam2.start()
            self.is_picam2 = True
            self.is_initialized = True
            logger.info("Initialized Raspberry Pi Camera Module 3 via Picamera2.")
        except Exception as e:
            logger.warning(f"Picamera2 unavailable ({e}). Attempting OpenCV VideoCapture on index {self.camera_index}...")
            self.is_picam2 = False

            # 2. Attempt OpenCV VideoCapture fallback
            try:
                if cv2 is not None:
                    self.cap = cv2.VideoCapture(self.camera_index)
                    if self.cap.isOpened():
                        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.PREVIEW_RESOLUTION[0])
                        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.PREVIEW_RESOLUTION[1])
                        self.is_initialized = True
                        logger.info(f"OpenCV VideoCapture opened on index {self.camera_index}.")
                    else:
                        logger.warning(f"OpenCV VideoCapture failed to open index {self.camera_index}.")
                        self.is_initialized = False
                else:
                    logger.warning("OpenCV cv2 module not found.")
                    self.is_initialized = False
            except Exception as cv_e:
                logger.error(f"OpenCV VideoCapture exception: {cv_e}")
                self.is_initialized = False

        if not self.is_initialized:
            logger.error("Camera initialization failed: no hardware camera stream could be established.")
            self.has_error = True
            self.running = False
            return False

        # Start continuous background frame buffer worker
        self.running = True
        self.thread = threading.Thread(target=self._frame_acquisition_loop, daemon=True)
        self.thread.start()
        logger.info("Camera background frame acquisition thread started.")
        return self.is_initialized

    def _frame_acquisition_loop(self):
        """Continuous background thread maintaining latest frame buffer without display GUI."""
        while self.running:
            frame = None
            try:
                if self.is_picam2 and self.picam2:
                    raw_arr = self.picam2.capture_array("main")
                    if raw_arr is not None:
                        if cv2 is not None:
                            frame = cv2.cvtColor(raw_arr, cv2.COLOR_RGB2BGR)
                        else:
                            frame = raw_arr

                elif self.cap and self.cap.isOpened():
                    ret, img = self.cap.read()
                    if ret and img is not None:
                        frame = img

            except Exception as e:
                logger.debug(f"Frame acquisition read exception: {e}")
                frame = None

            if frame is not None:
                self.consecutive_errors = 0
                self.has_error = False
                with self.lock:
                    self.current_frame = frame.copy()
            else:
                self.consecutive_errors += 1
                if self.consecutive_errors >= self.max_consecutive_errors and not self.has_error:
                    self.has_error = True
                    logger.error(f"Camera frame acquisition failure: {self.consecutive_errors} consecutive failed reads.")

            time.sleep(1.0 / config.CAMERA_FPS)

    def capture_frame(self):
        """
        Captures the latest preview frame for real-time page detection and alignment.
        Returns:
            np.ndarray or None: BGR image frame.
        """
        # Wait briefly for first frame if thread is starting
        for _ in range(5):
            with self.lock:
                if self.current_frame is not None:
                    return self.current_frame.copy()
            if not self.running:
                break
            time.sleep(0.05)

        with self.lock:
            if self.current_frame is not None:
                return self.current_frame.copy()

        logger.warning("Camera hardware frame unavailable (camera uninitialized or read error).")
        return None

    def capture_page(self):
        """
        Captures a high-resolution frame specifically for OCR and page preprocessing.
        Returns:
            np.ndarray or None: Real high-res BGR image frame, or None if camera is unavailable.
        """
        # If Picamera2 is active, capture array directly from main high-res stream
        if self.is_picam2 and self.picam2:
            try:
                arr = self.picam2.capture_array("main")
                if arr is not None:
                    if cv2 is not None:
                        high_res = cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)
                    else:
                        high_res = arr
                    logger.info(f"Captured real high-res page image (shape: {high_res.shape})")
                    return high_res
            except Exception as e:
                logger.error(f"High-res Picamera2 capture error: {e}")

        # Fallback to latest acquired frame from hardware video stream
        frame = self.capture_frame()
        if frame is not None:
            logger.info(f"Captured real page frame for OCR processing (shape: {frame.shape})")
        else:
            logger.warning("Camera hardware capture failed to acquire real frame.")
        return frame

    def release(self):
        """Releases all camera hardware resources and terminates background threads."""
        logger.info("Releasing camera resources...")
        self.running = False
        if self.thread and self.thread.is_alive():
            try:
                self.thread.join(timeout=1.0)
            except Exception:
                pass

        if self.is_picam2 and self.picam2:
            try:
                self.picam2.stop()
            except Exception as e:
                logger.debug(f"Note on Picamera2 stop: {e}")
            try:
                if hasattr(self.picam2, "close"):
                    self.picam2.close()
            except Exception as e:
                logger.debug(f"Note on Picamera2 close: {e}")
            self.picam2 = None

        if self.cap and self.cap.isOpened():
            try:
                self.cap.release()
            except Exception as e:
                logger.debug(f"Note on VideoCapture release: {e}")
            self.cap = None

        self.is_initialized = False
        logger.info("Camera resources released successfully.")

    # Convenience aliases for backwards compatibility
    def start(self):
        """Alias for initialize()."""
        return self.initialize()

    def get_frame(self):
        """Alias for capture_frame()."""
        return self.capture_frame()

    def capture_high_res(self):
        """Alias for capture_page()."""
        return self.capture_page()

    def stop(self):
        """Alias for release()."""
        self.release()

    def _generate_simulated_frame(self):
        """Generates a synthetic test book frame for offline development."""
        img = np.ones((config.PREVIEW_RESOLUTION[1], config.PREVIEW_RESOLUTION[0], 3), dtype=np.uint8) * 35
        h, w, _ = img.shape
        margin_x, margin_y = int(w * 0.15), int(h * 0.12)
        cv2.rectangle(img, (margin_x, margin_y), (w - margin_x, h - margin_y), (245, 245, 245), -1)
        cv2.putText(img, "VisionVoice Sample Book Page", (margin_x + 25, margin_y + 55),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (20, 20, 20), 2)
        cv2.putText(img, "Assisted reading device page for OCR test.", (margin_x + 25, margin_y + 100),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (50, 50, 50), 1)
        return img
