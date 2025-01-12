from pynput.keyboard import Controller

from models import GameSettings, HoldOrPress


class KeyboardController:
    def __init__(self):
        self.keyboard = Controller()
        self._left = False
        self._right = False
        self._sit = False

        self._settings = GameSettings.default()

    def hold(self, button: str):
        print(f"Удерживается кнопка {button}")
        self.keyboard.press(button.lower())

    def press(self, button: str):
        print(f"Нажата кнопка {button}")
        self.keyboard.tap(button.lower())

    def release(self, button: str):
        print(f"Отпущена кнопка {button}")
        self.keyboard.release(button.lower())

    def to_left(self):
        if self._left:
            return
        if self._right:
            self.un_right()
        s = self._settings.left
        if s.hold_or_press == HoldOrPress.HOLD:
            self.hold(self._settings.left.button)
        elif s.hold_or_press == HoldOrPress.PRESS:
            self.press(self._settings.left.button)
        else:
            raise ValueError(f"Некорректная настройка to_left [{s.hold_or_press}]")

        self._left = True

    def to_right(self):
        if self._right:
            return
        if self._left:
            self.un_left()

        s = self._settings.right
        if s.hold_or_press == HoldOrPress.HOLD:
            self.hold(self._settings.right.button)
        elif s.hold_or_press == HoldOrPress.PRESS:
            self.press(self._settings.right.button)
        else:
            raise ValueError(f"Некорректная настройка to_right [{s.hold_or_press}]")

        self._right = True

    def un_left(self):
        if not self._left:
            return
        s = self._settings.left
        if s.hold_or_press == HoldOrPress.HOLD:
            self.keyboard.release(self._settings.left.button)
        elif s.hold_or_press == HoldOrPress.PRESS:
            self.keyboard.tap(self._settings.left.button)
        else:
            raise ValueError(f"Некорректная настройка un_left [{s.hold_or_press}]")
        self._left = False

    def un_right(self):
        if not self._right:
            return
        s = self._settings.right
        if s.hold_or_press == HoldOrPress.HOLD:
            self.release(self._settings.right.button)
        elif s.hold_or_press == HoldOrPress.PRESS:
            self.keyboard.tap(self._settings.right.button)
        else:
            raise ValueError(f"Некорректная настройка un_right [{s.hold_or_press}]")
        self._right = False

    def sit(self):
        if self._sit:
            return

        s = self._settings.sit
        if s.hold_or_press == HoldOrPress.HOLD:
            self.keyboard.press(self._settings.sit.button)
        elif s.hold_or_press == HoldOrPress.PRESS:
            self.keyboard.tap(self._settings.sit.button)
        else:
            raise ValueError(f"Некорректная настройка sit [{s.hold_or_press}]")
        self._sit = True

    def stand(self):
        if not self._sit:
            return
        s = self._settings.sit
        if s.hold_or_press == HoldOrPress.HOLD:
            self.keyboard.release(self._settings.sit.button)
        elif s.hold_or_press == HoldOrPress.PRESS:
            self.keyboard.tap(self._settings.sit.button)
        else:
            raise ValueError(f"Некорректная настройка stand [{s.hold_or_press}]")
        self._sit = False

    def release_all(self):
        self.un_left()
        self.un_right()

    def set_settings(self, settings: GameSettings):
        self._settings = settings
