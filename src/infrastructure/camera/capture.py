import threading

import cv2
import numpy as np
from loguru import logger

from domain.camera import CameraMode

__all__ = ["CameraCaptureThread"]


class CameraCaptureThread:
    """
    Отдельный поток для постоянного чтения веб-камеры.
    Решает проблему буферизации Windows и убирает задержку в 100-150мс.
    """

    def __init__(self, camera_index: int = 0, mode: CameraMode | None = None):
        # CAP_DSHOW ускоряет захват на Windows
        self.cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        if mode:
            # Порядок важен: DirectShow применяет FOURCC только после размера и fps,
            # иначе молча остаётся на YUY2 (1080p в нём - 5 fps вместо 60)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, mode.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, mode.height)
            self.cap.set(cv2.CAP_PROP_FPS, mode.fps)
            if len(mode.fourcc) == 4:  # RGB24 и подобные задаются не FOURCC, а форматом по умолчанию
                self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc(*mode.fourcc))
        fourcc = int(self.cap.get(cv2.CAP_PROP_FOURCC)).to_bytes(4, "little").decode("ascii", "replace")
        logger.info(
            f"Камера {camera_index}: {int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x"
            f"{int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))} @ {self.cap.get(cv2.CAP_PROP_FPS):.0f} fps ({fourcc})"
        )
        self.fps: float = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.ret, self.frame = self.cap.read()
        self.is_running: bool = True
        self.frame_id: int = 0
        self._new_frame = threading.Condition()
        self.thread: threading.Thread = threading.Thread(target=self._update, daemon=True)

    def start(self):
        self.thread.start()

    def _update(self):
        while self.is_running:
            # Постоянно вычитываем кадры, оставляя только самый свежий
            ret, frame = self.cap.read()
            if ret:
                with self._new_frame:
                    self.ret = ret
                    self.frame = frame
                    self.frame_id += 1
                    self._new_frame.notify_all()

    def wait_for_frame(self, last_frame_id: int, timeout: float = 0.5) -> tuple[bool, np.ndarray, int]:
        """Блокируется до появления кадра новее last_frame_id (без холостого опроса)"""
        with self._new_frame:
            self._new_frame.wait_for(lambda: self.frame_id != last_frame_id or not self.is_running, timeout)
            return self.ret, self.frame, self.frame_id

    def stop(self):
        self.is_running = False
        self.thread.join()
        self.cap.release()
