import os
import time
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

logger = logging.getLogger("VisionVoice.PageProcessor")


def convert_to_grayscale(image):
    """
    Converts input image to single-channel 8-bit grayscale without mutating the original image.

    Args:
        image (np.ndarray): Input BGR, BGRA, or grayscale image.

    Returns:
        np.ndarray: Grayscale 8-bit single-channel image.
    """
    if image is None:
        raise ValueError("Cannot convert None image to grayscale.")

    if cv2 is None or np is None:
        return image

    if len(image.shape) == 2:
        return image.copy()
    elif len(image.shape) == 3:
        if image.shape[2] == 4:
            return cv2.cvtColor(image, cv2.COLOR_BGRA2GRAY)
        elif image.shape[2] == 3:
            return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        elif image.shape[2] == 1:
            return image[:, :, 0].copy()

    return image.copy()


def resize_or_upscale(image, target_min_dim=None, scale_factor=None):
    """
    Conditionally resizes or upscales a page image to improve OCR character stroke legibility.

    Args:
        image (np.ndarray): Input image.
        target_min_dim (int, optional): Minimum height/width dimension in pixels.
        scale_factor (float, optional): Explicit scale multiplier (e.g. 1.5, 2.0).

    Returns:
        np.ndarray: Resized image or copy of original if no scaling needed.
    """
    if image is None or cv2 is None:
        return image

    h, w = image.shape[:2]

    if scale_factor is not None and scale_factor > 1.0:
        new_w = int(w * scale_factor)
        new_h = int(h * scale_factor)
        return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_CUBIC)

    if target_min_dim is not None and min(h, w) < target_min_dim:
        factor = float(target_min_dim) / float(min(h, w))
        new_w = int(w * factor)
        new_h = int(h * factor)
        return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_CUBIC)

    return image.copy()


def reduce_noise(gray_image, method="bilateral"):
    """
    Applies edge-preserving or smoothing noise reduction to grayscale book page.

    Args:
        gray_image (np.ndarray): Grayscale image.
        method (str): 'bilateral', 'gaussian', 'median', 'nlm' (non-local means), or 'none'.

    Returns:
        np.ndarray: Denoised grayscale image.
    """
    if gray_image is None or cv2 is None:
        return gray_image

    if method == "bilateral":
        # Preserves crisp text character edges while smoothing paper texture & noise
        return cv2.bilateralFilter(gray_image, d=9, sigmaColor=75, sigmaSpace=75)
    elif method == "gaussian":
        return cv2.GaussianBlur(gray_image, (3, 3), 0)
    elif method == "median":
        return cv2.medianBlur(gray_image, 3)
    elif method in ["nlm", "non_local_means"]:
        return cv2.fastNlMeansDenoising(gray_image, h=10)
    elif method == "none":
        return gray_image.copy()

    return gray_image.copy()


def enhance_contrast(gray_image, method="clahe", remove_shadows=True):
    """
    Enhances contrast and corrects non-uniform lighting / page curve shadows on printed pages.

    Args:
        gray_image (np.ndarray): Denoised grayscale image.
        method (str): 'clahe', 'equalize', or 'none'.
        remove_shadows (bool): Whether to perform background illumination division.

    Returns:
        np.ndarray: Contrast-enhanced grayscale image.
    """
    if gray_image is None or cv2 is None:
        return gray_image

    working = gray_image.copy()

    # 1. Background Illumination Normalization (Shadow / Gutter removal)
    if remove_shadows:
        dilated = cv2.morphologyEx(working, cv2.MORPH_DILATE, np.ones((7, 7), np.uint8))
        bg = cv2.medianBlur(dilated, 21)
        diff = 255 - cv2.absdiff(working, bg)
        working = cv2.normalize(diff, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8U)

    # 2. Contrast Enhancement
    if method == "clahe":
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        return clahe.apply(working)
    elif method == "equalize":
        return cv2.equalizeHist(working)
    elif method == "none":
        return working

    return working


def apply_threshold(gray_image, method="adaptive"):
    """
    Applies adaptive or global binarization to separate text ink from paper background.

    Args:
        gray_image (np.ndarray): Grayscale contrast-enhanced image.
        method (str): 'adaptive' (Gaussian), 'adaptive_mean', 'otsu', or 'none'.

    Returns:
        np.ndarray: Binary or grayscale preprocessed image.
    """
    if gray_image is None or cv2 is None:
        return gray_image

    if method in ["adaptive", "adaptive_gaussian"]:
        return cv2.adaptiveThreshold(
            gray_image, 255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            blockSize=15,
            C=8
        )
    elif method == "adaptive_mean":
        return cv2.adaptiveThreshold(
            gray_image, 255,
            cv2.ADAPTIVE_THRESH_MEAN_C,
            cv2.THRESH_BINARY,
            blockSize=15,
            C=8
        )
    elif method == "otsu":
        _, binary = cv2.threshold(gray_image, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        return binary
    elif method in ["none", "grayscale"]:
        return gray_image.copy()

    return gray_image.copy()


def preprocess_page(
    image,
    upscale=False,
    target_min_dim=None,
    scale_factor=None,
    noise_reduction="bilateral",
    contrast_enhancement="clahe",
    threshold_method="adaptive",
    remove_shadows=True,
    save_debug=True,
    debug_path=None,
    return_stages=False
):
    """
    Modular OpenCV Preprocessing Pipeline for printed book pages.
    Evaluates:
      1. Grayscale conversion
      2. Optional resizing / upscaling
      3. Noise reduction (bilateral / gaussian / median / nlm)
      4. Contrast enhancement (CLAHE / shadow removal)
      5. Adaptive / global thresholding (adaptive Gaussian / adaptive Mean / Otsu)
      6. Headless debug artifact saving

    Args:
        image (np.ndarray): Input page image (original is kept untouched).
        upscale (bool): Whether to upscale small images for OCR resolution.
        target_min_dim (int, optional): Minimum dimension for upscaling (e.g. 1000px).
        scale_factor (float, optional): Direct scale multiplier (e.g. 1.5).
        noise_reduction (str): 'bilateral', 'gaussian', 'median', 'nlm', 'none'.
        contrast_enhancement (str): 'clahe', 'equalize', 'none'.
        threshold_method (str): 'adaptive', 'adaptive_mean', 'otsu', 'none'.
        remove_shadows (bool): Whether to perform background illumination division.
        save_debug (bool): If True, saves headless debug image to disk.
        debug_path (str, optional): Target path (defaults to 'debug/preprocessed.png').
        return_stages (bool): If True, returns dict with all intermediate stage images.

    Returns:
        np.ndarray or dict: Processed binary/enhanced image, or dictionary of stages.
    """
    if image is None:
        raise ValueError("preprocess_page received None as input image.")

    # Keep original image completely separate
    original = image.copy()

    # Step 1: Grayscale Conversion
    gray = convert_to_grayscale(original)

    # Step 2: Optional Resizing / Upscaling
    if upscale or target_min_dim is not None or scale_factor is not None:
        target_dim = target_min_dim if target_min_dim is not None else (1000 if upscale else None)
        scaled = resize_or_upscale(gray, target_min_dim=target_dim, scale_factor=scale_factor)
    else:
        scaled = gray.copy()

    # Step 3: Noise Reduction
    denoised = reduce_noise(scaled, method=noise_reduction)

    # Step 4: Contrast Enhancement & Shadow Removal
    enhanced = enhance_contrast(denoised, method=contrast_enhancement, remove_shadows=remove_shadows)

    # Step 5: Adaptive / Global Thresholding
    thresholded = apply_threshold(enhanced, method=threshold_method)

    # Step 6: Save Debug Image Headlessly
    if save_debug:
        save_path = debug_path or os.path.join(getattr(config, "BASE_DIR", "."), "debug", "preprocessed.png")
        try:
            debug_dir = os.path.dirname(save_path)
            if debug_dir:
                os.makedirs(debug_dir, exist_ok=True)
            cv2.imwrite(save_path, thresholded)
            logger.info(f"Saved preprocessed debug image to '{save_path}'")
        except Exception as e:
            logger.warning(f"Could not save debug image to '{save_path}': {e}")

    if return_stages:
        return {
            "original": original,
            "grayscale": gray,
            "scaled": scaled,
            "denoised": denoised,
            "enhanced": enhanced,
            "thresholded": thresholded,
            "result": thresholded
        }

    return thresholded


class PageProcessor:
    """
    Computer Vision Pipeline for VisionVoice.
    Performs 4-corner page detection, perspective unwarping, cropping,
    and adaptive image enhancement for Tesseract OCR text extraction.
    """

    def preprocess_page(self, image, **kwargs):
        """Modular preprocessing pipeline entry point on PageProcessor instance."""
        return preprocess_page(image, **kwargs)

    def enhance_for_ocr(self, warped_image, **kwargs):
        """
        Enhances unwarped page image specifically for Indic & English Tesseract OCR.
        Delegates to modular preprocess_page pipeline.
        """
        return preprocess_page(warped_image, **kwargs)

    def process_captured_page(self, image):
        """
        Executes the full computer-vision pipeline on a captured raw image.

        Returns:
            dict containing:
                - 'original': raw image
                - 'warped': perspective corrected rectangular image
                - 'enhanced': binary high-contrast image optimized for OCR
                - 'corners': array of 4 points [(x,y), ...]
                - 'saved_path': file path where corrected image was saved
        """
        if image is None:
            raise ValueError("PageProcessor received an empty or None image.")

        logger.info("Starting page detection and perspective correction pipeline...")

        # 1. Detect Corners
        corners = self.find_page_corners(image)

        # 2. Apply Perspective Warp
        warped = self.four_point_transform(image, corners)

        # 3. Apply OCR Image Enhancement via Modular Pipeline
        enhanced = self.preprocess_page(warped)

        # 4. Save Processed Artifact
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        save_filename = f"page_{timestamp}.jpg"
        save_path = os.path.join(config.CAPTURES_DIR, save_filename)
        cv2.imwrite(save_path, enhanced)
        logger.info(f"Processed page image saved to {save_path}")

        return {
            "original": image.copy(),
            "warped": warped,
            "enhanced": enhanced,
            "corners": corners,
            "saved_path": save_path
        }

    def find_page_corners(self, image):
        """
        Identifies the 4 corners of the open book page within the image.
        Uses multi-stage contour analysis with fallback mechanisms.
        """
        h, w = image.shape[:2]
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Multi-scale edge detection
        edges = cv2.Canny(blurred, 50, 150)
        dilated = cv2.dilate(edges, cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3)))

        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)

        frame_area = w * h

        for cnt in contours[:5]:
            area = cv2.contourArea(cnt)
            if area < (frame_area * 0.10):
                continue

            peri = cv2.arcLength(cnt, True)
            approx = cv2.approxPolyDP(cnt, 0.02 * peri, True)

            # Look for 4-point polygon contour
            if len(approx) == 4:
                logger.info("Found clean 4-corner page polygon contour.")
                return approx.reshape(4, 2)

        # Fallback: Minimum Bounding Rectangle on largest contour
        if len(contours) > 0 and cv2.contourArea(contours[0]) > (frame_area * 0.10):
            logger.info("Using Minimum Bounding Box for 4 corners.")
            rect = cv2.minAreaRect(contours[0])
            box = cv2.boxPoints(rect)
            return np.asarray(box, dtype=np.int32)

        # Final Fallback: Crop using framing margins
        logger.warning("Contour detection could not find distinct page edges. Using default ROI frame boundary.")
        mx = int(w * config.ROI_MARGIN_X)
        my = int(h * config.ROI_MARGIN_Y)
        return np.array([
            [mx, my],
            [w - mx, my],
            [w - mx, h - my],
            [mx, h - my]
        ], dtype=np.int32)

    def order_points(self, pts):
        """
        Orders 4 corner points in standard order:
        [top-left, top-right, bottom-right, bottom-left]
        """
        rect = np.zeros((4, 2), dtype="float32")

        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]  # Top-left has smallest sum
        rect[2] = pts[np.argmax(s)]  # Bottom-right has largest sum

        diff = np.diff(pts, axis=1)
        rect[1] = pts[np.argmin(diff)]  # Top-right has smallest difference
        rect[3] = pts[np.argmax(diff)]  # Bottom-left has largest difference

        return rect

    def four_point_transform(self, image, pts):
        """
        Applies a perspective transformation matrix (unwarp) to turn an angled
        book photo into a flat top-down rectangular page.
        """
        rect = self.order_points(pts)
        (tl, tr, br, bl) = rect

        # Compute width of new image
        width_A = np.sqrt(((br[0] - bl[0]) ** 2) + ((br[1] - bl[1]) ** 2))
        width_B = np.sqrt(((tr[0] - tl[0]) ** 2) + ((tr[1] - tl[1]) ** 2))
        max_width = max(int(width_A), int(width_B))

        # Compute height of new image
        height_A = np.sqrt(((tr[0] - br[0]) ** 2) + ((tr[1] - br[1]) ** 2))
        height_B = np.sqrt(((tl[0] - bl[0]) ** 2) + ((tl[1] - bl[1]) ** 2))
        max_height = max(int(height_A), int(height_B))

        # Target dimensions (top-down rectangular projection)
        dst = np.array([
            [0, 0],
            [max_width - 1, 0],
            [max_width - 1, max_height - 1],
            [0, max_height - 1]
        ], dtype="float32")

        M = cv2.getPerspectiveTransform(rect, dst)
        warped = cv2.warpPerspective(image, M, (max_width, max_height))
        return warped
