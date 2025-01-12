from dataclasses import dataclass
from enum import StrEnum

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout,
    QHBoxLayout, QLineEdit, QLabel,
    QRadioButton, QPushButton, QGroupBox,
    QButtonGroup, QMenu,
)
from loguru import logger


class SettingsType(StrEnum):
    left = "Наклон влево"
    right = "Наклон вправо"
    sit = "Приседание"


class HoldOrPress(StrEnum):
    HOLD = "Удержание"
    PRESS = "Нажатие"


@dataclass(slots=True)
class Setting:
    button: str
    hold_or_press: HoldOrPress

    def __repr__(self):
        return f'{self.button}: {self.hold_or_press}'


@dataclass
class GameSettings:
    left: Setting
    right: Setting
    sit: Setting

    @classmethod
    def default(cls):
        return GameSettings(
            left=Setting(button="Q", hold_or_press=HoldOrPress.HOLD),
            right=Setting(button="E", hold_or_press=HoldOrPress.HOLD),
            sit=Setting(button="C", hold_or_press=HoldOrPress.PRESS),
        )

    def update(self, t: SettingsType, setting: Setting):
        if t == SettingsType.left:
            self.left = setting
        elif t == SettingsType.right:
            self.right = setting
        elif t == SettingsType.sit:
            self.sit = setting
        else:
            raise ValueError(f"Некорректный тип настроек [{t}]")


class GameSettingsGroup(QGroupBox):
    updated = Signal(SettingsType, Setting)

    def __init__(self, parent, t: SettingsType):
        super().__init__(t, parent)
        self.layout = QVBoxLayout(self)

        self._t = t

        self.field_layout = QHBoxLayout()
        self.label = QLabel(self._t, self)
        self.field = QLineEdit(self)
        self.field.editingFinished.connect(self.on_edit)
        self.field.setMaxLength(1)
        self.field.setFixedWidth(50)

        self.field_layout.addWidget(self.label)
        self.field_layout.addWidget(self.field)
        self.layout.addLayout(self.field_layout)

        self.radio_layout = QHBoxLayout()
        self.hold_radio = QRadioButton(HoldOrPress.HOLD, self)
        self.press_radio = QRadioButton(HoldOrPress.PRESS, self)

        self.button_group = QButtonGroup(self)
        self.button_group.buttonClicked.connect(self.on_edit)
        self.button_group.addButton(self.hold_radio)
        self.button_group.addButton(self.press_radio)

        self.radio_layout.addWidget(self.hold_radio)
        self.radio_layout.addWidget(self.press_radio)
        self.layout.addLayout(self.radio_layout)

    def load_settings(self, setting: Setting):
        self.field.setText(setting.button)
        self.hold_radio.setChecked(setting.hold_or_press == HoldOrPress.HOLD)
        self.press_radio.setChecked(setting.hold_or_press == HoldOrPress.PRESS)

    def on_edit(self):
        h = HoldOrPress.HOLD if self.hold_radio.isChecked() else HoldOrPress.PRESS
        self.updated.emit(self._t, Setting(button=self.field.text(), hold_or_press=h))


class SettingsMenu(QMenu):
    settings_updated = Signal(GameSettings)

    def __init__(self, parent, game_settings: GameSettings = GameSettings.default()):
        super().__init__(parent)

        self.main_layout = QVBoxLayout(self)

        self._settings = game_settings

        self.to_left_group = GameSettingsGroup(self, SettingsType.left)
        self.to_right_group = GameSettingsGroup(self, SettingsType.right)
        self.sit_group = GameSettingsGroup(self, SettingsType.sit)

        for group in [self.to_left_group, self.to_right_group, self.sit_group]:
            group.updated.connect(self.handle_settings_update)

        self.main_layout.addWidget(self.to_left_group)
        self.main_layout.addWidget(self.to_right_group)
        self.main_layout.addWidget(self.sit_group)

        # Кнопки
        self.cancel_button = QPushButton("Отмена", self)
        self.cancel_button.clicked.connect(self.cancel_settings)
        self.main_layout.addWidget(self.cancel_button, alignment=Qt.AlignmentFlag.AlignCenter)

        self.load_subwidgets()

    def load_subwidgets(self):
        self.to_left_group.load_settings(self._settings.left)
        self.to_right_group.load_settings(self._settings.right)
        self.sit_group.load_settings(self._settings.sit)

    def handle_settings_update(self, t: SettingsType, update: Setting):
        logger.info(f"Обновление настроек [{t}] на [{update}]")
        self._settings.update(t, update)
        self.settings_updated.emit(self._settings)

    def cancel_settings(self):
        self._settings = GameSettings.default()
        self.load_subwidgets()
        self.settings_updated.emit(self._settings)


if __name__ == "__main__":
    app = QApplication([])
    widget = SettingsMenu(None)
    widget.show()
    app.exec()
