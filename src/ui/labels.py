"""Подписи для доменных значений. Только для отображения - в настройках хранятся сами значения"""

from domain.bindings import Action, KeyMode
from domain.pose import Stance

__all__ = ["ACTION_TITLES", "KEY_MODE_TITLES", "STANCE_TITLES"]

ACTION_TITLES = {
    Action.LEAN_LEFT: "Наклон влево",
    Action.LEAN_RIGHT: "Наклон вправо",
    Action.SIT: "Приседание",
}

KEY_MODE_TITLES = {
    KeyMode.HOLD: "Удержание",
    KeyMode.PRESS: "Нажатие",
}

STANCE_TITLES = {
    Stance.STAND: "стоит",
    Stance.CROUCH: "сидит",
    Stance.PRONE: "лежит",
}
