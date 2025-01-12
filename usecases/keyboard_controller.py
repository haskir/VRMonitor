from pynput.keyboard import Controller

from models import GameSettings, HoldOrPress


class KeyboardController:
    def __init__(self):
        self.keyboard = Controller()
        self._sit = False

        self._is_pressed = False

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
        s = self._settings.left
        if s.hold_or_press == HoldOrPress.HOLD:
            self.hold(s.button)
        elif s.hold_or_press == HoldOrPress.PRESS:
            self.press(s.button)
        else:
            raise ValueError(f"Некорректная настройка to_left [{s.hold_or_press}]")
        self._is_pressed = True

    def to_right(self):
        s = self._settings.right
        if s.hold_or_press == HoldOrPress.HOLD:
            self.hold(s.button)
        elif s.hold_or_press == HoldOrPress.PRESS:
            self.press(s.button)
        else:
            raise ValueError(f"Некорректная настройка to_right [{s.hold_or_press}]")
        self._is_pressed = True

    def un_left(self):
        s = self._settings.left
        if s.hold_or_press == HoldOrPress.HOLD:
            self.release(s.button)
        elif s.hold_or_press == HoldOrPress.PRESS:
            self.press(s.button)
        else:
            raise ValueError(f"Некорректная настройка un_left [{s.hold_or_press}]")

    def un_right(self):
        s = self._settings.right
        if s.hold_or_press == HoldOrPress.HOLD:
            self.release(s.button)
        elif s.hold_or_press == HoldOrPress.PRESS:
            self.press(s.button)
        else:
            raise ValueError(f"Некорректная настройка un_right [{s.hold_or_press}]")

    def sit(self):
        if self._sit:
            return

        s = self._settings.sit
        if s.hold_or_press == HoldOrPress.HOLD:
            self.keyboard.press(s.button)
        elif s.hold_or_press == HoldOrPress.PRESS:
            self.keyboard.tap(s.button)
        else:
            raise ValueError(f"Некорректная настройка sit [{s.hold_or_press}]")
        self._sit = True

    def stand(self):
        if not self._sit:
            return
        s = self._settings.sit
        if s.hold_or_press == HoldOrPress.HOLD:
            self.keyboard.release(s.button)
        elif s.hold_or_press == HoldOrPress.PRESS:
            self.keyboard.tap(s.button)
        else:
            raise ValueError(f"Некорректная настройка stand [{s.hold_or_press}]")
        self._sit = False

    def release_all(self):
        if not self._is_pressed:
            return
        self.un_left()
        self.un_right()
        self._is_pressed = False

    def set_settings(self, settings: GameSettings):
        self._settings = settings
