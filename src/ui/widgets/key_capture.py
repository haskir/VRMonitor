from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QPushButton, QWidget

__all__ = ["KeyCaptureButton", "key_title"]

# Клавиши Qt -> имена pydirectinput (буквы и цифры передаются как есть)
_SPECIAL_KEYS = {
    Qt.Key.Key_Space: "space",
    Qt.Key.Key_Control: "ctrl",
    Qt.Key.Key_Shift: "shift",
    Qt.Key.Key_Alt: "alt",
    Qt.Key.Key_Tab: "tab",
    Qt.Key.Key_CapsLock: "capslock",
    Qt.Key.Key_Left: "left",
    Qt.Key.Key_Right: "right",
    Qt.Key.Key_Up: "up",
    Qt.Key.Key_Down: "down",
    **{getattr(Qt.Key, f"Key_F{n}"): f"f{n}" for n in range(1, 13)},
}

_TITLES = {"space": "Пробел", "ctrl": "Ctrl", "shift": "Shift", "alt": "Alt", "tab": "Tab", "capslock": "Caps Lock"}

_WAITING_TEXT = "Жду клавишу…"


def key_title(button: str) -> str:
    """Подпись клавиши для интерфейса"""
    return _TITLES.get(button.lower(), button.upper())


def _key_name(event: QKeyEvent) -> str | None:
    if name := _SPECIAL_KEYS.get(Qt.Key(event.key())):
        return name
    # По коду клавиши, а не по тексту: так работает и в русской раскладке
    key = event.key()
    if Qt.Key.Key_A <= key <= Qt.Key.Key_Z or Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
        return chr(key).lower()
    return None


class KeyCaptureButton(QPushButton):
    """Кнопка с назначенной клавишей: нажмите на неё, затем нужную клавишу. Esc - отмена"""

    key_changed = Signal(str)

    def __init__(self, button: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._button = button
        self.setCheckable(True)
        self.setFixedWidth(120)  # Не меняется при «Жду клавишу…», соседние поля не прыгают
        self.setToolTip("Нажмите, затем нажмите клавишу на клавиатуре. Esc - отмена")
        self.toggled.connect(self._on_toggled)
        self._refresh()

    @property
    def button(self) -> str:
        return self._button

    def set_button(self, button: str):
        self._button = button
        self._refresh()

    def _refresh(self):
        self.setText(_WAITING_TEXT if self.isChecked() else key_title(self._button))

    def _on_toggled(self, checked: bool):
        self._refresh()
        if checked:
            self.setFocus()
            self.grabKeyboard()
        else:
            self.releaseKeyboard()

    def keyPressEvent(self, event: QKeyEvent):
        if not self.isChecked():
            super().keyPressEvent(event)
            return
        if event.key() == Qt.Key.Key_Escape:
            self.setChecked(False)
            return
        if (name := _key_name(event)) is None:
            return  # Неподдерживаемая клавиша - ждём другую
        self._button = name
        self.setChecked(False)
        self.key_changed.emit(name)

    def focusOutEvent(self, event):
        self.setChecked(False)
        super().focusOutEvent(event)
