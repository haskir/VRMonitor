from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import QWidget, QVBoxLayout, QSlider, QLineEdit, QApplication, QCheckBox
from PySide6.QtCore import Qt, Signal
import sys


class SitModeEditor(QWidget):
    is_enabled_changed = Signal(bool)
    new_y_signal = Signal(int)

    def __init__(self, parent=None, is_enabled: bool = True, max_y: int = -500):
        super().__init__(parent)

        self._is_enabled = is_enabled

        self.is_enabled_box = QCheckBox("Sit", self)
        self.is_enabled_box.stateChanged.connect(self._set_state)
        self.y_edit = QLineEdit("0", self)
        self.y_edit.setMaxLength(4)
        self.y_edit.setMaximumWidth(40)
        self.y_edit.setValidator(QIntValidator(max_y, 0))
        self.slider = QSlider(Qt.Orientation.Vertical, self)

        self.slider.setRange(max_y, 0)
        self.slider.setTickInterval(50)
        self.slider.setTickPosition(QSlider.TickPosition.TicksRight)

        self.layout = QVBoxLayout(self)

        self.layout.addWidget(self.is_enabled_box)
        self.layout.addWidget(self.y_edit)
        self.layout.addWidget(self.slider)

        self.slider.valueChanged.connect(self.update_line_edit)
        self.y_edit.textChanged.connect(self.update_slider)

        self._set_state(is_enabled)

    def _set_state(self, state: bool):
        self.is_enabled_box.setChecked(state)
        self._is_enabled = state
        self.slider.setEnabled(state)
        self.y_edit.setEnabled(state)
        self.is_enabled_changed.emit(state)

    def update_line_edit(self, value):
        # Обновляем значение в QLineEdit при изменении слайдера
        self.y_edit.setText(str(value))
        if self._is_enabled:
            self.new_y_signal.emit(value)

    def update_slider(self):
        # Обновляем значение в слайдере при изменении значения в QLineEdit
        value = int(self.y_edit.text())
        self.slider.setValue(value)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SitModeEditor()
    window.show()
    sys.exit(app.exec())
