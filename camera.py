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
    Camera Manager and Frame Acquisition Pipeline for VisionVoice.
    Provides standard cross-platform camera capture interface:
      - initialize()
      - capture_frame()
      - capture_page()
      - release()
    """

    def __init__(self, camera_index=config.CAMERA_INDEX):
        self.camera_index = camera_index
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
        Initializes camera device via OpenCV VideoCapture.
        Starts background frame acquisition thread.
        """
        if self.is_initialized and self.running:
            return True

        logger.info("Initializing camera subsystem...")
        self.has_error = False
        self.consecutive_errors = 0

        try:
            if cv2 is not None:
                self.cap = cv2.VideoCapture(self.camera_index)
                if self.cap.isOpened():
                    self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.PREVIEW_RESOLUTION[0])
                    self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.PREVIEW_RESOLUTION[1])
                    self.is_initialized = True
                    logger.info(f"OpenCV VideoCapture opened on camera index {self.camera_index}.")
                else:
                    logger.info(f"Camera index {self.camera_index} not opened. Using standby mode.")
                    self.is_initialized = False
            else:
                logger.info("OpenCV cv2 module not found. Operating in cloud/standby mode.")
                self.is_initialized = False
        except Exception as e:
            logger.debug(f"Camera initialization note: {e}")
            self.is_initialized = False

        if self.is_initialized:
            self.running = True
            self.thread = threading.Thread(target=self._frame_acquisition_loop, daemon=True)
            self.thread.start()
            logger.info("Camera background frame acquisition thread started.")

        return self.is_initialized

    def _frame_acquisition_loop(self):
        """Continuous background thread maintaining latest frame buffer."""
        while self.running:
            frame = None
            try:
                if self.cap and self.cap.isOpened():
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

            time.sleep(1.0 / config.CAMERA_FPS)

    def capture_frame(self):
        """
        Captures the latest preview frame for real-time page detection and alignment.
        """
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

        return None

    def capture_page(self):
        """
        Captures a high-resolution frame for OCR.
        """
        frame = self.capture_frame()
        if frame is not None:
            logger.info(f"Captured page frame for OCR processing (shape: {frame.shape})")
        return frame

    def release(self):
        """Releases camera hardware resources."""
        logger.info("Releasing camera resources...")
        self.running = False
        if self.thread and self.thread.is_alive():
            try:
                self.thread.join(timeout=1.0)
            except Exception:
                pass

        if self.cap and self.cap.isOpened():
            try:
                self.cap.release()
            except Exception:
                pass
            self.cap = None

        self.is_initialized = False

    def start(self):
        return self.initialize()

    def get_frame(self):
        return self.capture_frame()

    def capture_high_res(self):
        return self.capture_page()

    def stop(self):
        self.release()
