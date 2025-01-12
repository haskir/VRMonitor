from dataclasses import dataclass
from enum import StrEnum


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


__all__ = [
    "SettingsType",
    "HoldOrPress",
    "Setting",
    "GameSettings",
]
