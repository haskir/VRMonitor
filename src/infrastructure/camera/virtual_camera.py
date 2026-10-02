from collections.abc import Callable

import numpy as np
from loguru import logger

__all__ = ["VirtualCameraOutput"]


class VirtualCameraOutput:
    """
    Отдаёт кадры в виртуальную камеру, чтобы физическую камеру держало только это приложение.
    """

    def __init__(self, on_error: Callable[[str], None] | None = None):
        self._on_error = on_error
        self._cam = None
        self._format: tuple[int, int, int] | None = None  # ширина, высота, fps

    @property
    def is_open(self) -> bool:
        return self._cam is not None

    def send(self, frame: np.ndarray, fps: float) -> bool:
        """Отправляет BGR-кадр; при ошибке закрывает камеру, сообщает о ней и возвращает False"""
        height, width = frame.shape[:2]
        fmt = (width, height, max(round(fps), 1))
        try:
            if self._cam is None or self._format != fmt:
                self._open(*fmt)
            self._cam.send(frame)  # type: ignore
            return True
        except Exception as e:
            self.close()
            message = f"Не удалось вывести изображение в виртуальную камеру OBS: {e}"
            logger.error(message)
            if self._on_error:
                self._on_error(message)
            return False

    def _open(self, width: int, height: int, fps: int):
        import pyvirtualcam

        self.close()

        try:
            self._cam = pyvirtualcam.Camera(
                width, height, fps, fmt=pyvirtualcam.PixelFormat.BGR, backend="unitycapture"
            )
            logger.info("Виртуальная камера инициализирована через: UnityCapture")
        except Exception:
            self._cam = pyvirtualcam.Camera(width, height, fps, fmt=pyvirtualcam.PixelFormat.BGR, backend="obs")
            logger.info("Виртуальная камера инициализирована через: OBS Virtual Camera")

        self._format = (width, height, fps)

    def close(self):
        if self._cam is not None:
            self._cam.close()
            logger.info("Виртуальная камера закрыта")
        self._cam = None
        self._format = None
