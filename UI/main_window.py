from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QMainWindow, QWidget,
    QVBoxLayout, QPushButton,
    QLabel, QLineEdit, QHBoxLayout,
)
from loguru import logger

from consts import BASE_THRESHOLD

from UI.camera_list import CameraSelectWidget
from UI.window_list import WindowSelectWidget
from usecases.orchestrator import Orchestrator


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.resize(450, 450)
        self.setMaximumSize(800, 500)
        self.setWindowTitle("VR-монитор kek8")

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout(self.central_widget)

        # Контроллеры
        self._orchestrator = Orchestrator()

        # Виджет выбора окна
        self.window_select_widget = WindowSelectWidget(self, self._orchestrator.window_controller)

        # Виджет выбора камеры
        self.camera_select_widget = CameraSelectWidget(
            self,
            self._orchestrator.camera_provider,
            self._orchestrator.camera_controller
        )

        self.layout.addWidget(self.window_select_widget)
        self.layout.addWidget(self.camera_select_widget)

        # Toggle angle
        self.toggle_label = QLabel("Выберите пороговый угол", self)
        self._toggle_edit = QLineEdit("20", self)
        self._toggle_edit.setValidator(QIntValidator(0, 90))
        self._toggle_edit.editingFinished.connect(self._on_angle_changed)
        self._toggle_edit.setMaximumWidth(35)
        self._angle_layout = QHBoxLayout()

        # Toggle button
        self.is_on = False
        self._toggle_on_off = QPushButton("Включить", self)
        self._toggle_on_off.clicked.connect(self.toggle_on_off)
        self._toggle_on_off.setCheckable(True)

        self._is_camera_visible = False
        self._toggle_view = QPushButton("Показать камеру", self)
        self._toggle_view.clicked.connect(self.toggle_view)
        self._toggle_view.setCheckable(True)

        self._angle_layout.addWidget(self.toggle_label)
        self._angle_layout.addWidget(self._toggle_edit)
        self._angle_layout.addWidget(QLabel("градусов", self))
        self._angle_layout.addWidget(self._toggle_view)
        self._angle_layout.addWidget(self._toggle_on_off)
        self.layout.addLayout(self._angle_layout)

    def toggle_on_off(self):
        print("toggle_on_off clicked")
        if self.is_on:
            self._toggle_on_off.setText("Включить")
        else:
            self._toggle_on_off.setText("Выключить")
        self.is_on = not self.is_on
        self._orchestrator.toggle_on_off()

    def toggle_view(self):
        self._is_camera_visible = not self._is_camera_visible
        if self._is_camera_visible:
            self._toggle_view.setText("Скрыть камеру")
        else:
            self._toggle_view.setText("Показать камеру")
        self._orchestrator.set_camera_view(self._is_camera_visible)

    def _on_angle_changed(self):
        try:
            angle = int(self._toggle_edit.text())
            if not 0 <= angle <= 90:
                raise ValueError("Угол должен быть в диапазоне от 0 до 90")
        except ValueError:
            logger.debug("Некорректное значение угла")
            self._toggle_edit.setText(str(BASE_THRESHOLD))
        else:
            self._orchestrator.set_threshold(angle)
