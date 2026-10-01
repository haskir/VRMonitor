from loguru import logger
from PySide6.QtCore import Qt
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

from application.app import App
from consts import TARGET_GAME_NAME
from domain.bindings import GameBindings
from ui.bridge import QtBridge
from ui.camera_list import CameraSelectWidget
from ui.labels import STANCE_TITLES
from ui.settings_menu import SettingsMenu
from ui.sit_mode_editor import SitModeEditor

__all__ = ["MainWindow"]

MAX_ANGLE = 90


class MainWindow(QMainWindow):
    def __init__(self, app: App):
        super().__init__()
        self._app = app
        # Сигналы из потока камеры подключаем только к методам виджетов: тогда Qt вызывает их в потоке GUI
        self._bridge = QtBridge(app, self)
        settings = app.settings

        self.setMinimumSize(300, 300)
        self.setMaximumSize(800, 500)
        self.setWindowTitle("VR-монитор kek8")

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)
        self._layout = QVBoxLayout(self.central_widget)

        # Порог наклона и меню клавиш
        self._first_row = QHBoxLayout()
        self.toggle_label = QLabel("Выберите пороговый угол", self)
        self._angle_edit = QLineEdit(str(settings.angle_threshold), self)
        self._angle_edit.setValidator(QIntValidator(0, MAX_ANGLE))
        self._angle_edit.editingFinished.connect(self._on_angle_changed)
        self._angle_edit.setMaximumWidth(35)
        self._settings_button = QToolButton(self)
        self._settings_button.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_ArrowDown))
        self._settings_button.clicked.connect(self.show_settings)
        self._settings_button.setMaximumWidth(30)
        self._first_row.addWidget(self.toggle_label)
        self._first_row.addWidget(self._angle_edit)
        self._first_row.addWidget(QLabel("градусов", self))
        self._first_row.addWidget(self._settings_button)

        # Вкл/выкл распознавания и предпросмотр
        self._toggle_on_off = QPushButton("Включить", self)
        self._toggle_on_off.clicked.connect(self.toggle_on_off)
        self._toggle_on_off.setCheckable(True)
        self._toggle_view = QPushButton("Показать камеру", self)
        self._toggle_view.clicked.connect(self.toggle_view)
        self._toggle_view.setCheckable(True)

        # Детекция активного окна: клавиши уходят только в игру
        self._game_row = QHBoxLayout()
        self.only_in_game_widget = self._setting_checkbox(
            f"Только в {TARGET_GAME_NAME}",
            "only_in_game",
            f"Нажимать клавиши, только когда {TARGET_GAME_NAME} на переднем плане.\n"
            "При переключении на другое окно зажатые клавиши отпускаются.",
        )
        self.detect_stance_widget = self._setting_checkbox(
            "Учитывать позу",
            "detect_stance",
            "Определять позу персонажа по иконке слева от полосы здоровья.\n"
            "Пока персонаж лежит, приседания с камеры не нажимаются,\n"
            "а присед, сделанный вручную, принимается из игры.",
        )
        self.game_status_label = QLabel(self)
        self._bridge.game_active_changed.connect(self._update_game_status)
        self._bridge.stance_changed.connect(self._update_game_status)
        self._update_game_status()
        self._game_row.addWidget(self.only_in_game_widget)
        self._game_row.addWidget(self.detect_stance_widget)
        self._game_row.addStretch()
        self._game_row.addWidget(self.game_status_label)

        # Режим приседа
        self.sit_mode_widget = SitModeEditor(
            self,
            is_enabled=settings.sit_enabled,
            y=settings.sit_y,
            auto_calibrate=settings.auto_calibrate,
        )
        self.sit_mode_widget.is_enabled_changed.connect(lambda v: app.update(sit_enabled=v))
        self.sit_mode_widget.new_y_signal.connect(lambda v: app.update(sit_y=abs(v)))
        self.sit_mode_widget.auto_calibrate_changed.connect(lambda v: app.update(auto_calibrate=v))
        self._bridge.calibrated.connect(self.sit_mode_widget.set_y)

        # Выбор камеры: сохранённая могла пропасть, поэтому после выбора применяем то, что реально выбрано
        self.camera_select_widget = CameraSelectWidget(self, app.list_cameras())
        if settings.camera_index is not None:
            self.camera_select_widget.select_camera(settings.camera_index)
        self.camera_select_widget.select_mode(settings.camera_mode)
        if self.camera_select_widget.current_camera_index is not None:
            app.update(
                camera_index=self.camera_select_widget.current_camera_index,
                camera_mode=self.camera_select_widget.current_mode,
            )
        self.camera_select_widget.camera_changed.connect(lambda index: app.update(camera_index=index))
        self.camera_select_widget.mode_changed.connect(lambda mode: app.update(camera_mode=mode))

        self.visualization_widget = self._setting_checkbox("Визуализация", "visualize")

        # Вывод в OBS: камеру держит только это приложение, OBS берёт картинку из OBS Virtual Camera
        self.virtual_cam_widget = self._setting_checkbox(
            "Вывод в OBS",
            "virtual_cam",
            "Отдавать изображение камеры в OBS Virtual Camera (работает, пока детекция включена).\n"
            "В OBS добавьте источник «Устройство захвата видео» → «OBS Virtual Camera».\n"
            "Кнопка «Запустить виртуальную камеру» в самом OBS при этом должна быть выключена.",
        )
        self._bridge.virtual_cam_failed.connect(self._on_virtual_cam_failed)
        self.virtual_cam_mesh_widget = self._setting_checkbox(
            "Сетка в OBS", "virtual_cam_mesh", "Рисовать сетку лица на изображении для OBS"
        )

        self._second_row = QGridLayout()
        top = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
        bottom = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom
        self._second_row.addWidget(self.sit_mode_widget, 0, 0, 3, 1, alignment=Qt.AlignmentFlag.AlignLeft)
        self._second_row.addWidget(self.camera_select_widget, 0, 1, 1, 3, alignment=bottom)
        self._second_row.addWidget(self._toggle_view, 1, 1, 1, 1, alignment=top)
        self._second_row.addWidget(self.visualization_widget, 1, 2, 1, 1, alignment=top)
        self._second_row.addWidget(self._toggle_on_off, 1, 3, 1, 1, alignment=top)
        self._second_row.addWidget(self.virtual_cam_widget, 2, 1, 1, 1, alignment=Qt.AlignmentFlag.AlignHCenter)
        self._second_row.addWidget(self.virtual_cam_mesh_widget, 2, 2, 1, 1, alignment=Qt.AlignmentFlag.AlignHCenter)

        self._layout.addLayout(self._first_row)
        self._layout.addLayout(self._game_row)
        self._layout.addLayout(self._second_row)

    def _setting_checkbox(self, text: str, setting: str, tooltip: str | None = None) -> QCheckBox:
        """Галочка, напрямую связанная с булевой настройкой"""
        checkbox = QCheckBox(text, self)
        if tooltip:
            checkbox.setToolTip(tooltip)
        checkbox.setChecked(getattr(self._app.settings, setting))
        checkbox.toggled.connect(lambda value: self._app.update(**{setting: value}))
        return checkbox

    def show_settings(self):
        menu = SettingsMenu(self, self._app.settings.bindings)
        menu.bindings_updated.connect(self._on_bindings_updated)
        button_geometry = self._settings_button.geometry()
        global_point = self.mapToGlobal(button_geometry.topLeft())
        menu.setGeometry(global_point.x(), global_point.y() + button_geometry.height(), menu.width(), menu.height())
        menu.exec()  # type: ignore

    def _on_bindings_updated(self, bindings: GameBindings):
        self._app.update(bindings=bindings)

    def toggle_on_off(self, status: bool):
        self._toggle_on_off.setText("Выключить" if status else "Включить")
        self._app.set_running(status)

    def toggle_view(self, status: bool):
        self._toggle_view.setText("Скрыть камеру" if status else "Показать камеру")
        self._app.set_preview_visible(status)

    def _on_angle_changed(self):
        try:
            angle = int(self._angle_edit.text())
            if not 0 <= angle <= MAX_ANGLE:
                raise ValueError(f"Угол должен быть в диапазоне от 0 до {MAX_ANGLE}")
        except ValueError:
            logger.debug("Некорректное значение угла")
            self._angle_edit.setText(str(self._app.settings.angle_threshold))
        else:
            self._app.update(angle_threshold=angle)

    def _update_game_status(self, *_):
        if self._app.is_game_active:
            stance = STANCE_TITLES.get(self._app.stance)
            self.game_status_label.setText(f"{TARGET_GAME_NAME}: в фокусе" + (f", {stance}" if stance else ""))
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

    def closeEvent(self, event):
        self._bridge.shutdown()
