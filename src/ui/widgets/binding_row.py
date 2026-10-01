from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QWidget

from domain.bindings import KeyBinding, KeyMode
from ui.labels import KEY_MODE_HINTS, KEY_MODE_TITLES
from ui.widgets.key_capture import KeyCaptureButton

__all__ = ["BindingRow"]


class BindingRow(QWidget):
    """Клавиша и режим её нажатия для одного действия"""

    binding_changed = Signal(object)  # KeyBinding

    def __init__(self, binding: KeyBinding, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.key_button = KeyCaptureButton(binding.button, self)
        self.key_button.key_changed.connect(self._emit)
        self.mode_box = QComboBox(self)
        for mode in KeyMode:
            self.mode_box.addItem(KEY_MODE_TITLES[mode], mode)
            self.mode_box.setItemData(self.mode_box.count() - 1, KEY_MODE_HINTS[mode], Qt.ItemDataRole.ToolTipRole)
        self.mode_box.setCurrentIndex(self.mode_box.findData(binding.mode))
        self.mode_box.currentIndexChanged.connect(self._emit)

        layout.addWidget(self.key_button)
        layout.addWidget(self.mode_box, 1)

    def set_binding(self, binding: KeyBinding):
        self.key_button.set_button(binding.button)
        self.mode_box.blockSignals(True)
        self.mode_box.setCurrentIndex(self.mode_box.findData(binding.mode))
        self.mode_box.blockSignals(False)

    def _emit(self, *_):
        self.binding_changed.emit(KeyBinding(button=self.key_button.button, mode=self.mode_box.currentData()))
