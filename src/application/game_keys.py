from loguru import logger

from domain.bindings import GameBindings, KeyBinding, KeyMode
from domain.pose import Lean

from .ports import KeySender

__all__ = ["GameKeys"]


class GameKeys:
    """Помнит, какие действия сейчас включены в игре, и жмёт клавиши согласно привязкам"""

    def __init__(self, sender: KeySender, bindings: GameBindings | None = None):
        self._sender = sender
        self._bindings = bindings or GameBindings.default()
        self._lean = Lean.NONE
        self._sitting = False

    @property
    def bindings(self) -> GameBindings:
        return self._bindings

    @bindings.setter
    def bindings(self, bindings: GameBindings):
        self._bindings = bindings

    @property
    def lean(self) -> Lean:
        return self._lean

    @property
    def is_sitting(self) -> bool:
        return self._sitting

    def _activate(self, binding: KeyBinding):
        logger.debug(f"Включение {binding}")
        if binding.mode == KeyMode.HOLD:
            self._sender.key_down(binding.button)
        else:
            self._sender.tap(binding.button)

    def _deactivate(self, binding: KeyBinding):
        logger.debug(f"Выключение {binding}")
        if binding.mode == KeyMode.HOLD:
            self._sender.key_up(binding.button)
        else:
            self._sender.tap(binding.button)  # Переключатель отменяется повторным нажатием

    def _lean_binding(self, lean: Lean) -> KeyBinding | None:
        return {Lean.LEFT: self._bindings.left, Lean.RIGHT: self._bindings.right}.get(lean)

    def set_lean(self, lean: Lean):
        if lean == self._lean:
            return
        # Сначала отменяем текущий наклон, иначе в игре включатся оба
        if current := self._lean_binding(self._lean):
            self._deactivate(current)
        if target := self._lean_binding(lean):
            self._activate(target)
        self._lean = lean

    def set_sitting(self, sitting: bool):
        if sitting == self._sitting:
            return
        logger.info("Сажусь" if sitting else "Встаю")
        if sitting:
            self._activate(self._bindings.sit)
        else:
            self._deactivate(self._bindings.sit)
        self._sitting = sitting

    def release_held(self):
        """
        Отпускает удерживаемые (HOLD) клавиши, например при уходе из игры.
        Переключатели (PRESS) не трогаем: их состояние хранит игра, а нажатие вне её напечатало бы букву
        """
        lean = self._lean_binding(self._lean)
        if lean and lean.mode == KeyMode.HOLD:
            self._sender.key_up(lean.button)
            self._lean = Lean.NONE
        if self._sitting and self._bindings.sit.mode == KeyMode.HOLD:
            self._sender.key_up(self._bindings.sit.button)
            self._sitting = False

    def assume_sitting(self, sitting: bool) -> bool:
        """
        Принимает состояние приседа, увиденное в игре, без нажатий; возвращает True, если оно изменилось.
        Нужно только для переключателя (PRESS): игрок мог сам нажать присед или встать из положения лёжа,
        и наше состояние разошлось с игровым. Для HOLD правда - это зажатая клавиша, её не трогаем
        """
        if self._bindings.sit.mode != KeyMode.PRESS or self._sitting == sitting:
            return False
        self._sitting = sitting
        return True
