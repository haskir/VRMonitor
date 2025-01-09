import cv2
from loguru import logger


class CameraProvider:
    @staticmethod
    def _test_camera(index: int) -> bool:
        try:
            cap = cv2.VideoCapture(1)
            while True:
                ret, frame = cap.read()
                if not ret:
                    logger.info(f"Ошибка: Невозможно считать кадр с камеры[{index}]!")
                    return False
                return True
        except Exception as e:
            logger.error(f"Ошибка при тестировании камеры[{index}]: {e}")
            return False

    @staticmethod
    def get_available_cameras_ids() -> list[int]:
        max_cameras = 10
        available = []
        for i in range(max_cameras):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)

            if not cap.read()[0]:
                continue

            available.append(i)
            cap.release()

            logger.info(f"Camera {i:02d} is OK!")
        if not available:
            logger.error("Нет доступных камер!")

        return available