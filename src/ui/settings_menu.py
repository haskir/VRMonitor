from loguru import logger
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from domain.bindings import Action, GameBindings, KeyBinding, KeyMode
from ui.labels import ACTION_TITLES, KEY_MODE_TITLES

__all__ = ["BindingEditor", "SettingsMenu"]


class BindingEditor(QGroupBox):
    """Клавиша и режим (удержание/нажатие) для одного действия"""

    updated = Signal(object, object)  # Action, KeyBinding

    def __init__(self, parent: QWidget, action: Action):
        super().__init__(ACTION_TITLES[action], parent)
        self._action = action
        self._layout = QVBoxLayout(self)

        self.field_layout = QHBoxLayout()
        self.label = QLabel(ACTION_TITLES[action], self)
        self.field = QLineEdit(self)
        self.field.editingFinished.connect(self._on_edit)
        self.field.setMaxLength(1)
        self.field.setFixedWidth(50)
        self.field_layout.addWidget(self.label)
        self.field_layout.addWidget(self.field)
        self._layout.addLayout(self.field_layout)

        self.radio_layout = QHBoxLayout()
        self.hold_radio = QRadioButton(KEY_MODE_TITLES[KeyMode.HOLD], self)
        self.press_radio = QRadioButton(KEY_MODE_TITLES[KeyMode.PRESS], self)
        self.button_group = QButtonGroup(self)
        self.button_group.buttonClicked.connect(self._on_edit)
        self.button_group.addButton(self.hold_radio)
        self.button_group.addButton(self.press_radio)
        self.radio_layout.addWidget(self.hold_radio)
        self.radio_layout.addWidget(self.press_radio)
        self._layout.addLayout(self.radio_layout)

    def load(self, binding: KeyBinding):
        self.field.setText(binding.button)
        self.hold_radio.setChecked(binding.mode == KeyMode.HOLD)
        self.press_radio.setChecked(binding.mode == KeyMode.PRESS)

    def _on_edit(self):
        if not self.field.text():
            return
        mode = KeyMode.HOLD if self.hold_radio.isChecked() else KeyMode.PRESS
        self.updated.emit(self._action, KeyBinding(button=self.field.text(), mode=mode))


class SettingsMenu(QMenu):
    bindings_updated = Signal(object)  # GameBindings

    def __init__(self, parent: QWidget | None, bindings: GameBindings):
        super().__init__(parent)
        self._bindings = bindings
        self.main_layout = QVBoxLayout(self)

        self._editors = {action: BindingEditor(self, action) for action in Action}
        for editor in self._editors.values():
            editor.updated.connect(self._on_binding_updated)
            self.main_layout.addWidget(editor)

        self.reset_button = QPushButton("Сбросить", self)
        self.reset_button.setToolTip("Вернуть клавиши по умолчанию")
        self.reset_button.clicked.connect(self._reset)
        self.main_layout.addWidget(self.reset_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self._load_editors()

    def _load_editors(self):
        for action, editor in self._editors.items():
            editor.load(self._bindings.get(action))

    def _on_binding_updated(self, action: Action, binding: KeyBinding):
        logger.info(f"Обновление привязки [{ACTION_TITLES[action]}] на [{binding}]")
        self._bindings = self._bindings.with_binding(action, binding)
        self.bindings_updated.emit(self._bindings)

    def _reset(self):
        self._bindings = GameBindings.default()
        self._load_editors()
        self.bindings_updated.emit(self._bindings)
