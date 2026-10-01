from loguru import logger
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from consts import BASE_THRESHOLD, TARGET_GAME_NAME
from models import AppSettings, GameSettings
from ui.camera_list import CameraSelectWidget
from ui.settings_menu import SettingsMenu
from ui.sit_mode_editor import SitModeEditor
from usecases.orchestrator import Orchestrator

__all__ = ["MainWindow"]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setMinimumSize(300, 300)
        self.setMaximumSize(800, 500)
        self.setWindowTitle("VR-монитор kek8")

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self._layout = QVBoxLayout(self.central_widget)
        self.setLayout(self._layout)

        # Настройки сохраняются с небольшой задержкой, чтобы не писать файл на каждый шаг слайдера
        self._settings: AppSettings = AppSettings.load()
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(500)
        self._save_timer.timeout.connect(self._settings.save)

        # Контроллеры
        self._orchestrator: Orchestrator = Orchestrator(self, self._settings.game)
        camera_controller = self._orchestrator.camera_controller
        camera_controller.angle_threshold = self._settings.angle_threshold
        camera_controller.set_y_threshold(self._settings.sit_y)
        camera_controller.set_auto_calibrate(self._settings.auto_calibrate)
        camera_controller.set_visualize_detection(self._settings.visualize)
        camera_controller.set_virtual_cam(self._settings.virtual_cam)
        camera_controller.set_virtual_cam_mesh(self._settings.virtual_cam_mesh)
        self._orchestrator.set_is_sit_controlling(self._settings.sit_enabled)
        self._orchestrator.set_only_in_game(self._settings.only_in_game)

        # Toggle angle
        self._first_row = QHBoxLayout()
        self.toggle_label = QLabel("Выберите пороговый угол", self)
        self._toggle_edit = QLineEdit(str(self._settings.angle_threshold), self)
        self._toggle_edit.setValidator(QIntValidator(0, 90))
        self._toggle_edit.editingFinished.connect(self._on_angle_changed)
        self._toggle_edit.setMaximumWidth(35)
        self._settings_button = QToolButton(self)
        self._settings_button.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_ArrowDown))
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

        # Детекция активного окна: клавиши уходят только в игру
        self._game_row = QHBoxLayout()
        self.only_in_game_widget = QCheckBox(f"Только в {TARGET_GAME_NAME}", self)
        self.only_in_game_widget.setToolTip(
            f"Нажимать клавиши, только когда {TARGET_GAME_NAME} на переднем плане.\n"
            "При переключении на другое окно зажатые клавиши отпускаются."
        )
        self.only_in_game_widget.setChecked(self._settings.only_in_game)
        self.only_in_game_widget.toggled.connect(self._orchestrator.set_only_in_game)
        self.only_in_game_widget.toggled.connect(lambda v: self._update_settings(only_in_game=v))
        self.game_status_label = QLabel(self)
        self._orchestrator.game_active_changed.connect(self._on_game_active_changed)
        self._on_game_active_changed(self._orchestrator.is_game_active)
        self._game_row.addWidget(self.only_in_game_widget)
        self._game_row.addStretch()
        self._game_row.addWidget(self.game_status_label)

        # Вторая строка
        self._second_row = QGridLayout()

        # Виджет режима сидения
        self.sit_mode_widget = SitModeEditor(
            self,
            is_enabled=self._settings.sit_enabled,
            y=self._settings.sit_y,
            auto_calibrate=self._settings.auto_calibrate,
        )
        self.sit_mode_widget.is_enabled_changed.connect(self._orchestrator.set_is_sit_controlling)
        self.sit_mode_widget.is_enabled_changed.connect(lambda v: self._update_settings(sit_enabled=v))
        self.sit_mode_widget.new_y_signal.connect(self._orchestrator.camera_controller.set_y_threshold)
        self.sit_mode_widget.new_y_signal.connect(lambda v: self._update_settings(sit_y=abs(v)))
        self.sit_mode_widget.auto_calibrate_changed.connect(self._orchestrator.camera_controller.set_auto_calibrate)
        self.sit_mode_widget.auto_calibrate_changed.connect(lambda v: self._update_settings(auto_calibrate=v))
        self._orchestrator.y_threshold_calibrated.connect(self.sit_mode_widget.set_y)

        # Виджет выбора камеры
        self.camera_select_widget = CameraSelectWidget(
            self,
            self._orchestrator.camera_provider,
            self._orchestrator.camera_controller,
        )
        if self._settings.camera_index is not None:
            self.camera_select_widget.select_camera(self._settings.camera_index)
        self.camera_select_widget.select_mode(self._settings.camera_mode)
        self.camera_select_widget.camera_changed.connect(lambda index: self._update_settings(camera_index=index))
        self.camera_select_widget.mode_changed.connect(lambda mode: self._update_settings(camera_mode=mode))

        # Виджет вкл/выкл визуализации
        self.visualization_widget = QCheckBox("Визуализация", self)
        self.visualization_widget.setChecked(self._settings.visualize)
        self.visualization_widget.toggled.connect(self._orchestrator.camera_controller.set_visualize_detection)
        self.visualization_widget.toggled.connect(lambda v: self._update_settings(visualize=v))

        # Вывод в OBS: камеру держит только это приложение, OBS берёт картинку из OBS Virtual Camera
        self.virtual_cam_widget = QCheckBox("Вывод в OBS", self)
        self.virtual_cam_widget.setToolTip(
            "Отдавать изображение камеры в OBS Virtual Camera (работает, пока детекция включена).\n"
            "В OBS добавьте источник «Устройство захвата видео» → «OBS Virtual Camera».\n"
            "Кнопка «Запустить виртуальную камеру» в самом OBS при этом должна быть выключена."
        )
        self.virtual_cam_widget.setChecked(self._settings.virtual_cam)
        self.virtual_cam_widget.toggled.connect(self._orchestrator.camera_controller.set_virtual_cam)
        self.virtual_cam_widget.toggled.connect(lambda v: self._update_settings(virtual_cam=v))
        self._orchestrator.virtual_cam_failed.connect(self._on_virtual_cam_failed)

        self.virtual_cam_mesh_widget = QCheckBox("Сетка в OBS", self)
        self.virtual_cam_mesh_widget.setToolTip("Рисовать сетку лица на изображении для OBS")
        self.virtual_cam_mesh_widget.setChecked(self._settings.virtual_cam_mesh)
        self.virtual_cam_mesh_widget.toggled.connect(self._orchestrator.camera_controller.set_virtual_cam_mesh)
        self.virtual_cam_mesh_widget.toggled.connect(lambda v: self._update_settings(virtual_cam_mesh=v))

        self._second_row.addWidget(self.sit_mode_widget, 0, 0, 3, 1, alignment=Qt.AlignmentFlag.AlignLeft)
        self._second_row.addWidget(
            self.camera_select_widget,
            0,
            1,
            1,
            3,
            alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
        )
        self._second_row.addWidget(
            self._toggle_view,
            1,
            1,
            1,
            1,
            alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
        )
        self._second_row.addWidget(
            self.visualization_widget,
            1,
            2,
            1,
            1,
            alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
        )
        self._second_row.addWidget(
            self._toggle_on_off,
            1,
            3,
            1,
            1,
            alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop,
        )

        self._second_row.addWidget(self.virtual_cam_widget, 2, 1, 1, 1, alignment=Qt.AlignmentFlag.AlignHCenter)
        self._second_row.addWidget(self.virtual_cam_mesh_widget, 2, 2, 1, 1, alignment=Qt.AlignmentFlag.AlignHCenter)

        # Главный layout
        self._layout.addLayout(self._first_row)
        self._layout.addLayout(self._game_row)
        self._layout.addLayout(self._second_row)

    def show_settings(self):
        d = SettingsMenu(self, self._settings.game)
        d.game_settings_updated.connect(self._orchestrator.update_game_settings)
        d.game_settings_updated.connect(self._on_game_settings_updated)
        button_geometry = self._settings_button.geometry()
        global_point = self.mapToGlobal(button_geometry.topLeft())
        dialog_x = global_point.x()
        dialog_y = global_point.y() + button_geometry.height()
        d.setGeometry(dialog_x, dialog_y, d.width(), d.height())
        d.exec()  # type: ignore

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
            self._update_settings(angle_threshold=angle)

    def _on_game_active_changed(self, is_active: bool):
        if is_active:
            self.game_status_label.setText(f"{TARGET_GAME_NAME}: в фокусе")
            self.game_status_label.setStyleSheet("color: #2e9e44; font-weight: bold;")
        else:
            self.game_status_label.setText(f"{TARGET_GAME_NAME}: не в фокусе")
            self.game_status_label.setStyleSheet("color: gray;")

    def _on_virtual_cam_failed(self, message: str):
        self.virtual_cam_widget.setChecked(False)
        QMessageBox.warning(
            self,
            "Вывод в OBS",
            f"{message}\n\nПроверьте, что OBS Studio установлен, "
            "а его собственная виртуальная камера («Запустить виртуальную камеру») выключена.",
        )

    def _on_game_settings_updated(self, game: GameSettings):
        self._update_settings(game=game)

    def _update_settings(self, **changes):
        for name, value in changes.items():
            setattr(self._settings, name, value)
        self._save_timer.start()

    def closeEvent(self, event):
        self._save_timer.stop()
        self._settings.save()
        self._orchestrator.camera_controller.off(wait=True)
        # Только отпускаем зажатое: повторное нажатие переключателя ушло бы в другое окно
        self._orchestrator.keyboard_controller.release_held()
