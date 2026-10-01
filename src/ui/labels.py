"""Подписи для доменных значений. Только для отображения - в настройках хранятся сами значения"""

from domain.bindings import Action, KeyMode
from domain.pose import Stance

__all__ = ["ACTION_TITLES", "KEY_MODE_HINTS", "KEY_MODE_TITLES", "STANCE_TITLES"]

ACTION_TITLES = {
    Action.LEAN_LEFT: "Влево",
    Action.LEAN_RIGHT: "Вправо",
    Action.SIT: "Клавиша",
}

KEY_MODE_TITLES = {
    KeyMode.HOLD: "Удерживать",
    KeyMode.PRESS: "Нажимать",
}

KEY_MODE_HINTS = {
    KeyMode.HOLD: "Клавиша зажата, пока действие активно (как в игре с режимом «удержание»)",
    KeyMode.PRESS: "Одно нажатие включает действие, повторное - выключает (режим «переключение»)",
}

STANCE_TITLES = {
    Stance.STAND: "стоит",
    Stance.CROUCH: "сидит",
    Stance.PRONE: "лежит",
}
