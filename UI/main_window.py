from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QMainWindow, QApplication, QWidget,
    QVBoxLayout, QPushButton, QLabel, QLineEdit, QHBoxLayout, )
from loguru import logger

from UI.camera_list import CameraSelectWidget
from UI.window_list import WindowSelectWidget
from consts import BASE_THRESHOLD
from usecases.camera_controller import CameraController
from usecases.keyboard_controller import KeyboardController
from usecases.windows_provider import WindowsProvider
from usecases.cameras_provider import CameraProvider


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.resize(400, 300)
        self.setMaximumSize(800, 500)
        self.setWindowTitle("VR-монитор kek8")

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout(self.central_widget)

        # Контроллеры
        self._windows_provider = WindowsProvider()
        self._cameras_provider = CameraProvider()
        self._keyboard_controller = KeyboardController()
        self._camera_controller = CameraController(
            self._keyboard_controller,
            self._windows_provider,
            BASE_THRESHOLD,
        )

        # Виджет выбора окна
        self.window_select_widget = WindowSelectWidget(self, self._windows_provider)

        # Виджет выбора камеры
        self.camera_select_widget = CameraSelectWidget(self, self._cameras_provider)
        self.camera_select_widget.new_camera_selected.connect(self.camera_selected)
        self._camera_controller.new_camera_selected(self.camera_select_widget.current_camera_index)

        self.layout.addWidget(self.window_select_widget)
        self.layout.addWidget(self.camera_select_widget)

        # Toggle angle
        self.toggle_label = QLabel("Выберите пороговый угол", self)
        self._toggle_edit = QLineEdit("20", self)
        self._toggle_edit.setValidator(QIntValidator(0, 90))
        self._toggle_edit.editingFinished.connect(self._on_angle_changed)
        self._toggle_edit.setMaximumWidth(35)
        self._angle_layout = QHBoxLayout()

        # Таймер обновления списка окон
        self._toggle_button = QPushButton("Вкл", self)
        self._toggle_button.clicked.connect(self.toggle_on_off)
        self._toggle_button.setCheckable(True)

        self._angle_layout.addWidget(self.toggle_label)
        self._angle_layout.addWidget(self._toggle_edit)
        self._angle_layout.addWidget(QLabel("градусов", self))
        self._angle_layout.addWidget(self._toggle_button)
        self.layout.addLayout(self._angle_layout)

    def camera_selected(self, camera_id: int):
        logger.info(f"Выбрана камера {camera_id}")
        self._camera_controller.new_camera_selected(camera_id)

    def toggle_on_off(self, checked):
        if checked:
            self._toggle_button.setText("Выкл")
            self._camera_controller.on()
            self._keyboard_controller.on()
        else:
            self._toggle_button.setText("Вкл")
            self._camera_controller.off()
            self._keyboard_controller.off()

    @property
    def angle(self) -> int:
        try:
            return int(self._toggle_edit.text())
        except ValueError:
            return BASE_THRESHOLD

    def _on_angle_changed(self):
        try:
            angle = int(self._toggle_edit.text())
            if angle < 0 or angle > 90:
                raise ValueError
        except ValueError:
            self._toggle_edit.setText(str(self._camera_controller.threshold))
        else:
            self._camera_controller.threshold = angle
