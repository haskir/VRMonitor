from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from application.app import App
from consts import TARGET_GAME_NAME
from domain.bindings import Action, GameBindings, KeyBinding
from domain.pose import Y_SCALE
from ui.bridge import QtBridge
from ui.camera_list import CameraSelectWidget
from ui.labels import ACTION_TITLES, STANCE_TITLES
from ui.preview_window import PreviewWindow
from ui.widgets.binding_row import BindingRow
from ui.widgets.threshold_gauge import ThresholdGauge

__all__ = ["MainWindow"]

LIVE_REFRESH_MS = 100  # Как часто обновлять живые подсказки

BLANK_FRAME_WARNING = (
    "Камера отдаёт чёрный кадр. Скорее всего, её заняла другая программа — например, OBS. "
    "Уберите физическую камеру из OBS, чтобы освободить её для распознавания. "
    "Для вывода изображения в OBS используйте источник «Захват окна», выбрав окно «Предпросмотр камеры»."
)
MIN_ANGLE, MAX_ANGLE = 1, 60
LABEL_COLUMN_WIDTH = 64  # Шкалы в разных секциях начинаются с одной вертикали

STYLE = """
QPushButton#primary { font-size: 15px; font-weight: 600; padding: 10px 18px; }
QPushButton#primary:checked { background: #2f9e44; color: white; border: 1px solid #2b8a3e; }
QLabel[chip] { border-radius: 10px; padding: 3px 10px; }
QLabel[chip="ok"] { background: rgba(47, 158, 68, 0.22); color: palette(text); }
QLabel[chip="warn"] { background: rgba(232, 89, 12, 0.25); color: palette(text); }
QLabel[chip="off"] { background: rgba(128, 128, 128, 0.18); color: palette(placeholder-text); }
QLabel[hint] { color: palette(placeholder-text); }
QLabel[value] { font-weight: 600; min-width: 42px; }
"""


def _hint(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setProperty("hint", True)
    label.setWordWrap(True)
    return label


def _set_chip(label: QLabel, text: str, state: str):
    label.setText(text)
    if label.property("chip") != state:
        label.setProperty("chip", state)
        label.style().unpolish(label)
        label.style().polish(label)


class MainWindow(QMainWindow):
    def __init__(self, app: App):
        super().__init__()
        self._app = app
        # Сигналы из потока камеры подключаем только к методам виджетов: тогда Qt вызывает их в потоке GUI
        self._bridge = QtBridge(app, self)

        self.setWindowTitle("VR-монитор kek8")
        self.setStyleSheet(STYLE)
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)

        layout.addLayout(self._build_header())
        layout.addWidget(self._build_camera_group())
        layout.addWidget(self._build_lean_group())
        layout.addWidget(self._build_sit_group())
        layout.addWidget(self._build_game_group())
        layout.addStretch()

        self._preview_window = PreviewWindow()
        self._bridge.preview_frame.connect(self._preview_window.show_frame)

        self._bridge.game_active_changed.connect(self._refresh_status)
        self._bridge.stance_changed.connect(self._refresh_status)
        self._bridge.calibrated.connect(self._on_calibrated)
        self._bridge.virtual_cam_failed.connect(self._on_virtual_cam_failed)

        self._live_timer = QTimer(self)
        self._live_timer.timeout.connect(self._refresh_live)
        self._live_timer.start(LIVE_REFRESH_MS)
        self._refresh_live()

        self.setMinimumWidth(480)
        self.adjustSize()

    # --- Построение ---

    def _build_header(self) -> QVBoxLayout:
        self.run_button = QPushButton("Включить распознавание", self)
        self.run_button.setObjectName("primary")
        self.run_button.setCheckable(True)
        self.run_button.toggled.connect(self._on_run_toggled)

        self.face_chip = QLabel(self)
        self.game_chip = QLabel(self)
        chips = QHBoxLayout()
        chips.addWidget(self.face_chip)
        chips.addWidget(self.game_chip)
        chips.addStretch()

        self.blank_warning = QLabel(BLANK_FRAME_WARNING, self)
        self.blank_warning.setProperty("chip", "warn")
        self.blank_warning.setWordWrap(True)
        self.blank_warning.setVisible(False)

        header = QVBoxLayout()
        header.addWidget(self.run_button)
        header.addLayout(chips)
        header.addWidget(self.blank_warning)
        return header

    def _build_camera_group(self) -> QGroupBox:
        settings = self._app.settings
        group = QGroupBox("Камера", self)
        grid = QGridLayout(group)

        # Сохранённая камера могла пропасть, поэтому после выбора применяем то, что реально выбрано
        self.camera_select = CameraSelectWidget(group, self._app.list_cameras())
        if settings.camera_index is not None:
            self.camera_select.select_camera(settings.camera_index)
        self.camera_select.select_mode(settings.camera_mode)
        if self.camera_select.current_camera_index is not None:
            self._app.update(
                camera_index=self.camera_select.current_camera_index,
                camera_mode=self.camera_select.current_mode,
            )
        self.camera_select.camera_changed.connect(lambda index: self._app.update(camera_index=index))
        self.camera_select.mode_changed.connect(lambda mode: self._app.update(camera_mode=mode))

        self.preview_button = QPushButton("Показать камеру", group)
        self.preview_button.setCheckable(True)
        self.preview_button.setToolTip("Окно с изображением камеры; работает, пока распознавание включено")
        self.preview_button.toggled.connect(self._on_preview_toggled)
        self.visualize_box = self._setting_checkbox(
            group, "Разметка в окне камеры", "visualize", "Сетка лица, линии приседа и угол наклона поверх изображения"
        )
        self.virtual_cam_box = self._setting_checkbox(
            group,
            "Виртуальная камера",
            "virtual_cam",
            "Отдавать изображение в виртуальную камеру (Discord/Zoom).\n"
            "Если нужно вывести изображение в сам OBS, используйте источник «Захват окна» (окно предпросмотра).",
        )
        self.virtual_cam_mesh_box = self._setting_checkbox(
            group,
            "Сетка лица в вирт. камере",
            "virtual_cam_mesh",
            "Рисовать сетку лица на изображении виртуальной камеры",
        )
        self.virtual_cam_mesh_box.setEnabled(settings.virtual_cam)
        self.virtual_cam_box.toggled.connect(self.virtual_cam_mesh_box.setEnabled)

        grid.addWidget(self.camera_select, 0, 0, 1, 2)
        grid.addWidget(self.preview_button, 1, 0)
        grid.addWidget(self.visualize_box, 1, 1)
        grid.addWidget(self.virtual_cam_box, 2, 0)
        grid.addWidget(self.virtual_cam_mesh_box, 2, 1)
        return group

    def _build_lean_group(self) -> QGroupBox:
        settings = self._app.settings
        group = QGroupBox("Наклоны", self)
        grid = QGridLayout(group)

        self.angle_gauge = ThresholdGauge(MIN_ANGLE, MAX_ANGLE, settings.angle_threshold, group)
        self.angle_gauge.setToolTip("Наклон головы, после которого персонаж наклоняется")
        self.angle_value = QLabel(group)
        self.angle_value.setProperty("value", True)
        self.angle_live = _hint()
        self.angle_gauge.value_changed.connect(self._on_angle_changed)
        self._show_angle(self.angle_gauge.value)

        self.left_row = self._binding_row(group, Action.LEAN_LEFT)
        self.right_row = self._binding_row(group, Action.LEAN_RIGHT)

        grid.setColumnMinimumWidth(0, LABEL_COLUMN_WIDTH)
        grid.addWidget(QLabel("Порог", group), 0, 0)
        grid.addWidget(self.angle_gauge, 0, 1)
        grid.addWidget(self.angle_value, 0, 2)
        grid.addWidget(self.angle_live, 1, 1, 1, 2)
        grid.addWidget(QLabel(ACTION_TITLES[Action.LEAN_LEFT], group), 2, 0)
        grid.addWidget(self.left_row, 2, 1, 1, 2)
        grid.addWidget(QLabel(ACTION_TITLES[Action.LEAN_RIGHT], group), 3, 0)
        grid.addWidget(self.right_row, 3, 1, 1, 2)
        grid.setColumnStretch(1, 1)
        return group

    def _build_sit_group(self) -> QGroupBox:
        settings = self._app.settings
        group = QGroupBox("Приседания", self)
        group.setCheckable(True)
        group.setChecked(settings.sit_enabled)
        group.toggled.connect(lambda enabled: self._app.update(sit_enabled=enabled))
        grid = QGridLayout(group)

        self.sit_gauge = ThresholdGauge(1, Y_SCALE, settings.sit_y, group)
        self.sit_gauge.setToolTip(
            "Линия на высоте кадра (слева - верх, справа - низ).\nГолова опустилась правее линии - персонаж садится"
        )
        self.sit_value = QLabel(group)
        self.sit_value.setProperty("value", True)
        self.sit_live = _hint()
        self.sit_gauge.value_changed.connect(self._on_sit_threshold_changed)
        self._show_sit_threshold(settings.sit_y)

        self.auto_calibrate_box = self._setting_checkbox(
            group,
            "Авто-калибровка",
            "auto_calibrate",
            "Если голова неподвижна 20 секунд стоя, её положение считается верхним,\n"
            "и линия приседа сдвигается вместе с ним (зелёная отметка на шкале)",
        )
        self.sit_row = self._binding_row(group, Action.SIT)

        grid.setColumnMinimumWidth(0, LABEL_COLUMN_WIDTH)
        grid.addWidget(QLabel("Линия", group), 0, 0)
        grid.addWidget(self.sit_gauge, 0, 1)
        grid.addWidget(self.sit_value, 0, 2)
        grid.addWidget(self.sit_live, 1, 1, 1, 2)
        grid.addWidget(self.auto_calibrate_box, 2, 1, 1, 2)
        grid.addWidget(QLabel(ACTION_TITLES[Action.SIT], group), 3, 0)
        grid.addWidget(self.sit_row, 3, 1, 1, 2)
        grid.setColumnStretch(1, 1)
        return group

    def _build_game_group(self) -> QGroupBox:
        group = QGroupBox(TARGET_GAME_NAME, self)
        layout = QVBoxLayout(group)
        layout.addWidget(
            self._setting_checkbox(
                group,
                f"Нажимать клавиши только в {TARGET_GAME_NAME}",
                "only_in_game",
                f"Клавиши уходят, только когда {TARGET_GAME_NAME} на переднем плане.\n"
                "При переключении на другое окно зажатые клавиши отпускаются.",
            )
        )
        layout.addWidget(
            self._setting_checkbox(
                group,
                "Учитывать позу персонажа",
                "detect_stance",
                "Поза определяется по иконке слева от полосы здоровья.\n"
                "Пока персонаж лежит, приседания с камеры не нажимаются,\n"
                "а присед, сделанный вручную, принимается из игры.",
            )
        )
        reset = QPushButton("Клавиши по умолчанию", group)
        reset.setFlat(True)
        reset.clicked.connect(self._reset_bindings)
        layout.addWidget(reset, alignment=Qt.AlignmentFlag.AlignLeft)
        return group

    def _setting_checkbox(self, parent: QWidget, text: str, setting: str, tooltip: str | None = None) -> QCheckBox:
        """Галочка, напрямую связанная с булевой настройкой"""
        checkbox = QCheckBox(text, parent)
        if tooltip:
            checkbox.setToolTip(tooltip)
        checkbox.setChecked(getattr(self._app.settings, setting))
        checkbox.toggled.connect(lambda value: self._app.update(**{setting: value}))
        return checkbox

    def _binding_row(self, parent: QWidget, action: Action) -> BindingRow:
        row = BindingRow(self._app.settings.bindings.get(action), parent)
        row.binding_changed.connect(lambda binding: self._on_binding_changed(action, binding))
        return row

    # --- Реакция на действия пользователя ---

    def _on_run_toggled(self, running: bool):
        self.run_button.setText("Выключить распознавание" if running else "Включить распознавание")
        self._app.set_running(running)
        self._refresh_live()

    def _on_preview_toggled(self, visible: bool):
        self.preview_button.setText("Скрыть камеру" if visible else "Показать камеру")
        self._app.set_preview_visible(visible)
        if visible:
            self._preview_window.show()
        else:
            self._preview_window.hide()

    def _on_angle_changed(self, angle: int):
        self._show_angle(angle)
        self._app.update(angle_threshold=angle)

    def _on_sit_threshold_changed(self, threshold: int):
        self._show_sit_threshold(threshold)
        self._app.update(sit_y=threshold)

    def _on_binding_changed(self, action: Action, binding: KeyBinding):
        self._app.update(bindings=self._app.settings.bindings.with_binding(action, binding))

    def _reset_bindings(self):
        bindings = GameBindings.default()
        self._app.update(bindings=bindings)
        for row, action in ((self.left_row, Action.LEAN_LEFT), (self.right_row, Action.LEAN_RIGHT)):
            row.set_binding(bindings.get(action))
        self.sit_row.set_binding(bindings.sit)

    # --- Реакция на события приложения ---

    def _on_calibrated(self, threshold: int):
        self.sit_gauge.set_value(threshold, emit=False)
        self._show_sit_threshold(threshold)
        self._app.update(sit_y=threshold)

    def _on_virtual_cam_failed(self, message: str):
        self.virtual_cam_box.setChecked(False)
        QMessageBox.warning(
            self,
            "Виртуальная камера",
            f"{message}\n\nПроверьте, что драйвера виртуальной камеры установлены, "
            "и они не заблокированы другими программами.",
        )

    # --- Отображение ---

    def _show_angle(self, angle: int):
        self.angle_value.setText(f"{angle}°")

    def _show_sit_threshold(self, threshold: int):
        self.sit_value.setText(f"{threshold * 100 // Y_SCALE}%" if threshold else "—")

    def _refresh_live(self):
        live = self._app.live_head() if self._app.is_running else None
        pose = live.pose if live else None

        if pose is None:
            self.angle_gauge.set_live(None)
            self.sit_gauge.set_live(None)
            idle = "Лицо не найдено" if self._app.is_running else "Положение головы появится после включения"
            self.angle_live.setText(idle)
            self.sit_live.setText(idle)
        else:
            tilt = abs(pose.tilt)
            side = "влево" if pose.tilt > 0 else "вправо"
            self.angle_gauge.set_live(tilt)
            self.angle_live.setText(
                f"Сейчас {tilt:.0f}° {side}" + (" — наклон" if self.angle_gauge.is_live_active else "")
            )
            self.sit_gauge.set_live(pose.y)
            if not self._app.settings.sit_y:
                self.sit_live.setText("Линия не задана: встаньте ровно и перетащите её чуть ниже головы")
            else:
                self.sit_live.setText(
                    f"Голова на {pose.y * 100 / Y_SCALE:.0f}% высоты кадра"
                    + (" — присед" if self.sit_gauge.is_live_active else "")
                )
        self.sit_gauge.set_reference(live.base_y if live else None)
        self._refresh_status()

    def _refresh_status(self, *_):
        is_blank = self._app.is_camera_blank
        if self.blank_warning.isHidden() == is_blank:
            self.blank_warning.setVisible(is_blank)
            self.adjustSize()

        if not self._app.is_running:
            _set_chip(self.face_chip, "Камера выключена", "off")
        elif is_blank:
            _set_chip(self.face_chip, "Чёрный кадр с камеры", "warn")
        elif self._app.live_head().pose is None:
            _set_chip(self.face_chip, "Лицо не найдено", "warn")
        else:
            _set_chip(self.face_chip, "Лицо найдено", "ok")

        if self._app.is_game_active:
            stance = STANCE_TITLES.get(self._app.stance)
            _set_chip(self.game_chip, f"{TARGET_GAME_NAME} в фокусе" + (f", {stance}" if stance else ""), "ok")
        elif self._app.settings.only_in_game:
            _set_chip(self.game_chip, f"{TARGET_GAME_NAME} не в фокусе — клавиши не нажимаются", "off")
        else:
            _set_chip(self.game_chip, f"{TARGET_GAME_NAME} не в фокусе", "off")

    def closeEvent(self, event):
        self._preview_window.close()
        self._live_timer.stop()
        self._bridge.shutdown()
