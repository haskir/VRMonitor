from pynput.keyboard import Controller

from models import GameSettings


class KeyboardController:
    def __init__(self):
        self.keyboard = Controller()
        self._left = False
        self._right = False
        self._sit = False

        self._settings = GameSettings.default()

    def to_left(self):
        if self._right:
            self.un_right()
        self._left = True

        s = self._settings.left
        if s.hold_or_press == s.HoldOrPress.HOLD:
            self.keyboard.press(self._settings.left.button)
        elif s.hold_or_press == s.HoldOrPress.PRESS:
            self.keyboard.tap(self._settings.left.button)
        else:
            raise ValueError(f"Некорректная настройка to_left [{s.hold_or_press}]")

    def to_right(self):
        if self._left:
            self.un_left()
        self._right = True

        s = self._settings.right
        if s.hold_or_press == s.HoldOrPress.HOLD:
            self.keyboard.press(self._settings.right.button)
        elif s.hold_or_press == s.HoldOrPress.PRESS:
            self.keyboard.tap(self._settings.right.button)
        else:
            raise ValueError(f"Некорректная настройка to_right [{s.hold_or_press}]")

    def un_left(self):
        if not self._left:
            return
        self._left = False
        s = self._settings.left
        if s.hold_or_press == s.HoldOrPress.HOLD:
            self.keyboard.release(self._settings.left.button)
        elif s.hold_or_press == s.HoldOrPress.PRESS:
            self.keyboard.tap(self._settings.left.button)
        else:
            raise ValueError(f"Некорректная настройка un_left [{s.hold_or_press}]")

    def un_right(self):
        if not self._right:
            return
        self._right = False
        s = self._settings.right
        if s.hold_or_press == s.HoldOrPress.HOLD:
            self.keyboard.release(self._settings.right.button)
        elif s.hold_or_press == s.HoldOrPress.PRESS:
            self.keyboard.tap(self._settings.right.button)
        else:
            raise ValueError(f"Некорректная настройка un_right [{s.hold_or_press}]")

    def sit(self):
        if self._sit:
            return
        self._sit = True

        s = self._settings.sit
        if s.hold_or_press == s.HoldOrPress.HOLD:
            self.keyboard.press(self._settings.sit.button)
        elif s.hold_or_press == s.HoldOrPress.PRESS:
            self.keyboard.tap(self._settings.sit.button)
        else:
            raise ValueError(f"Некорректная настройка sit [{s.hold_or_press}]")

    def stand(self):
        if not self._sit:
            return
        self._sit = False
        s = self._settings.sit
        if s.hold_or_press == s.HoldOrPress.HOLD:
            self.keyboard.release(self._settings.sit.button)
        elif s.hold_or_press == s.HoldOrPress.PRESS:
            self.keyboard.tap(self._settings.sit.button)
        else:
            raise ValueError(f"Некорректная настройка stand [{s.hold_or_press}]")

    def release_all(self):
        self.un_left()
        self.un_right()

    def set_settings(self, settings: GameSettings):
        self._settings = settings
