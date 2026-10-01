import cv2
import numpy as np

__all__ = ["PreviewWindow"]

PREVIEW_TITLE = "Тестирование выбранной камеры"
PREVIEW_WIDTH = 960  # Начальная ширина окна предпросмотра камеры


class PreviewWindow:
    """Окно OpenCV с предпросмотром. Живёт в потоке камеры: окна cv2 привязаны к создавшему их потоку"""

    def __init__(self):
        self._is_shown = False

    def show(self, frame: np.ndarray):
        if not self._is_shown:
            # Окно масштабируемое, иначе кадр 1080p/1440p не влезет в экран
            cv2.namedWindow(PREVIEW_TITLE, cv2.WINDOW_NORMAL)
            height, width = frame.shape[:2]
            preview_width = min(width, PREVIEW_WIDTH)
            cv2.resizeWindow(PREVIEW_TITLE, preview_width, height * preview_width // width)
            self._is_shown = True
        cv2.imshow(PREVIEW_TITLE, frame)
        # waitKey стоит ~2 мс, поэтому крутим цикл событий окна только когда оно показано
        cv2.waitKey(1)

    def hide(self):
        if self._is_shown:
            cv2.destroyWindow(PREVIEW_TITLE)
            self._is_shown = False

    def close(self):
        self.hide()
        cv2.destroyAllWindows()
