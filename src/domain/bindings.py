from dataclasses import dataclass, replace
from enum import StrEnum

__all__ = [
    "Action",
    "GameBindings",
    "KeyBinding",
    "KeyMode",
]


class KeyMode(StrEnum):
    HOLD = "hold"  # Клавиша зажата, пока действие активно
    PRESS = "press"  # Клавиша-переключатель: нажатие включает действие, повторное - выключает


class Action(StrEnum):
    LEAN_LEFT = "left"
    LEAN_RIGHT = "right"
    SIT = "sit"


@dataclass(frozen=True, slots=True)
class KeyBinding:
    button: str
    mode: KeyMode

    def __repr__(self):
        return f"{self.button}: {self.mode}"


@dataclass(frozen=True, slots=True)
class GameBindings:
    left: KeyBinding
    right: KeyBinding
    sit: KeyBinding

    @classmethod
    def default(cls) -> "GameBindings":
        return cls(
            left=KeyBinding(button="Q", mode=KeyMode.HOLD),
            right=KeyBinding(button="E", mode=KeyMode.HOLD),
            sit=KeyBinding(button="C", mode=KeyMode.PRESS),
        )

    def get(self, action: Action) -> KeyBinding:
        return getattr(self, action.value)

    def with_binding(self, action: Action, binding: KeyBinding) -> "GameBindings":
        return replace(self, **{action.value: binding})
