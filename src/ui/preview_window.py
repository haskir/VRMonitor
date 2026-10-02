import cv2
import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

__all__ = ["PreviewWindow"]


class PreviewWindow(QWidget):
    """Окно для предпросмотра камеры на базе Qt. Потокобезопасно обновляется через сигналы."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Предпросмотр камеры")
        self.resize(960, 540)
        self.setMinimumSize(320, 240)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.label.setStyleSheet("background-color: black;")
        layout.addWidget(self.label)

    def show_frame(self, frame: np.ndarray):
        # Если окно скрыто, не тратим ресурсы на конвертацию кадра
        if self.isHidden():
            return

        height, width, ch = frame.shape
        bytes_per_line = ch * width

        # BGR (OpenCV) -> RGB (Qt)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb_frame.data, width, height, bytes_per_line, QImage.Format.Format_RGB888)

        # Масштабируем изображение с сохранением пропорций
        pixmap = QPixmap.fromImage(qimg).scaled(
            self.label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        self.label.setPixmap(pixmap)
