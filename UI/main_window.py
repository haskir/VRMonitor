from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QMainWindow, QWidget,
    QVBoxLayout, QPushButton,
    QLabel, QLineEdit, QHBoxLayout, QToolButton, QGridLayout, QCheckBox,
)
from loguru import logger

from UI.sit_mode_editor import SitModeEditor
from consts import BASE_THRESHOLD

from UI.camera_list import CameraSelectWidget
from UI.settings_menu import SettingsMenu
from usecases.orchestrator import Orchestrator


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setMinimumSize(300, 300)
        self.setMaximumSize(800, 500)
        self.setWindowTitle("VR-монитор kek8")

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # Контроллеры
        self._orchestrator = Orchestrator(self)

        # Toggle angle
        self._first_row = QHBoxLayout()
        self.toggle_label = QLabel("Выберите пороговый угол", self)
        self._toggle_edit = QLineEdit("20", self)
        self._toggle_edit.setValidator(QIntValidator(0, 90))
        self._toggle_edit.editingFinished.connect(self._on_angle_changed)
        self._toggle_edit.setMaximumWidth(35)
        self._settings_button = QToolButton(self)
        self._settings_button.setIcon(
            self.style().standardIcon(self.style().StandardPixmap.SP_ArrowDown))
        self._settings_button.clicked.connect(self.show_settings)
        self._settings_button.setMaximumWidth(30)

        # Toggle button
        self._toggle_on_off = QPushButton("Включить", self)
        self._toggle_on_off.clicked.connect(self.toggle_on_off)
        self._toggle_on_off.setCheckable(True)

        self._toggle_view = QPushButton("Показать камеру", self)
        self._toggle_view.clicked.connect(self.toggle_view)
        self._toggle_view.setCheckable(True)

        self._first_row.addWidget(self.toggle_label)
        self._first_row.addWidget(self._toggle_edit)
        self._first_row.addWidget(QLabel("градусов", self))
        self._first_row.addWidget(self._settings_button)

        # Вторая строка
        self._second_row = QGridLayout()

        # Виджет режима сидения
        self.sit_mode_widget = SitModeEditor(self)
        self.sit_mode_widget.is_enabled_changed.connect(self._orchestrator.set_is_sit_controlling)
        self.sit_mode_widget.new_y_signal.connect(self._orchestrator.camera_controller.set_y_threshold)

        # Виджет выбора камеры
        self.camera_select_widget = CameraSelectWidget(
            self,
            self._orchestrator.camera_provider,
            self._orchestrator.camera_controller
        )

        # Виджет вкл/выкл визуализации
        self.visualization_widget = QCheckBox("Визуализация", self)
        self.visualization_widget.stateChanged.connect(
            self._orchestrator.camera_controller.set_visualize_detection
        )

        self._second_row.addWidget(self.sit_mode_widget, 0, 0, 2, 1,
                                   alignment=Qt.AlignmentFlag.AlignLeft)
        self._second_row.addWidget(self.camera_select_widget, 0, 1, 1, 3,
                                   alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom)
        self._second_row.addWidget(self._toggle_view, 1, 1, 1, 1,
                                   alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self._second_row.addWidget(self.visualization_widget, 1, 2, 1, 1,
                                   alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)
        self._second_row.addWidget(self._toggle_on_off, 1, 3, 1, 1,
                                   alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        # Главный layout
        self.layout.addLayout(self._first_row)
        self.layout.addLayout(self._second_row)

    def show_settings(self):
        d = SettingsMenu(self)
        d.game_settings_updated.connect(self._orchestrator.update_game_settings)
        button_geometry = self._settings_button.geometry()
        global_point = self.mapToGlobal(button_geometry.topLeft())
        dialog_x = global_point.x()
        dialog_y = global_point.y() + button_geometry.height()
        d.setGeometry(dialog_x, dialog_y, d.width(), d.height())
        d.exec()

    def toggle_on_off(self, status: bool):
        if status:
            self._toggle_on_off.setText("Выключить")
        else:
            self._toggle_on_off.setText("Включить")
        self._orchestrator.toggle_on_off()

    def toggle_view(self, status: bool):
        if status:
            self._toggle_view.setText("Скрыть камеру")
        else:
            self._toggle_view.setText("Показать камеру")
        self._orchestrator.set_camera_view(status)

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

    def closeEvent(self, event):
        self._orchestrator.camera_controller.off()
        self._orchestrator.keyboard_controller.release_all()
