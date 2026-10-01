import time

import pydirectinput

from models import GameSettings, HoldOrPress

# ОТКЛЮЧАЕМ искусственные задержки pydirectinput, чтобы не тормозить цикл обработки камеры
pydirectinput.PAUSE = 0.0
pydirectinput.FAILSAFE = False  # type: ignore


class KeyboardController:
    def __init__(self, settings: GameSettings | None = None):
        self._sit: bool = False
        self._current_lean: str | None = None  # Состояние наклона: "left", "right" или None
        self._settings: GameSettings = settings if settings else GameSettings.default()

    def hold(self, button: str):
        print(f"Удерживается кнопка {button}")
        pydirectinput.keyDown(button.lower())

    def press(self, button: str):
        print(f"Нажата кнопка {button}")
        pydirectinput.keyDown(button.lower())
        # Играм на DirectX нужна микро-задержка, чтобы заметить "клик" (иначе он слишком быстрый)
        time.sleep(0.015)
        pydirectinput.keyUp(button.lower())

    def release(self, button: str):
        print(f"Отпущена кнопка {button}")
        pydirectinput.keyUp(button.lower())

    def to_left(self):
        # Если мы были наклонены вправо, сначала отменяем правый наклон!
        if self._current_lean == "right":
            self.un_right()

        s = self._settings.left
        if s.hold_or_press == HoldOrPress.HOLD:
            self.hold(s.button)
        elif s.hold_or_press == HoldOrPress.PRESS:
            self.press(s.button)
        else:
            raise ValueError(f"Некорректная настройка to_left [{s.hold_or_press}]")

        self._current_lean = "left"

    def to_right(self):
        # Если мы были наклонены влево, сначала отменяем левый наклон!
        if self._current_lean == "left":
            self.un_left()

        s = self._settings.right
        if s.hold_or_press == HoldOrPress.HOLD:
            self.hold(s.button)
        elif s.hold_or_press == HoldOrPress.PRESS:
            self.press(s.button)
        else:
            raise ValueError(f"Некорректная настройка to_right [{s.hold_or_press}]")

        self._current_lean = "right"

    def un_left(self):
        s = self._settings.left
        if s.hold_or_press == HoldOrPress.HOLD:
            self.release(s.button)
        elif s.hold_or_press == HoldOrPress.PRESS:
            self.press(s.button)  # Для режима PRESS (переключатель) нажимаем еще раз, чтобы отменить

    def un_right(self):
        s = self._settings.right
        if s.hold_or_press == HoldOrPress.HOLD:
            self.release(s.button)
        elif s.hold_or_press == HoldOrPress.PRESS:
            self.press(s.button)

    def sit(self):
        if self._sit:
            return
        print("Сажусь")

        s = self._settings.sit
        if s.hold_or_press == HoldOrPress.HOLD:
            self.hold(s.button)
        elif s.hold_or_press == HoldOrPress.PRESS:
            self.press(s.button)
        else:
            raise ValueError(f"Некорректная настройка sit [{s.hold_or_press}]")

        self._sit = True

    def stand(self):
        if not self._sit:
            return
        print("Встаю")

        s = self._settings.sit
        if s.hold_or_press == HoldOrPress.HOLD:
            self.release(s.button)
        elif s.hold_or_press == HoldOrPress.PRESS:
            self.press(s.button)
        else:
            raise ValueError(f"Некорректная настройка stand [{s.hold_or_press}]")

        self._sit = False

    def release_all(self):
        """Возвращает голову в нейтральное положение"""
        if self._current_lean == "left":
            self.un_left()
        elif self._current_lean == "right":
            self.un_right()

        self._current_lean = None

    def set_settings(self, settings: GameSettings):
        self._settings = settings

    def release_held(self):
        """
        Отпускает удерживаемые (HOLD) клавиши, например при уходе из игры.
        Переключатели (PRESS) не трогаем: их состояние хранит игра, а нажатие вне её напечатало бы букву
        """
        lean = {"left": self._settings.left, "right": self._settings.right}.get(self._current_lean or "")
        if lean and lean.hold_or_press == HoldOrPress.HOLD:
            self.release(lean.button)
            self._current_lean = None
        if self._sit and self._settings.sit.hold_or_press == HoldOrPress.HOLD:
            self.release(self._settings.sit.button)
            self._sit = False

    def assume_sitting(self, is_sitting: bool) -> bool:
        """
        Принимает состояние приседа, увиденное в игре, без нажатий; возвращает True, если оно изменилось.
        Нужно только для переключателя (PRESS): игрок мог сам нажать присед или встать из положения лёжа,
        и наше состояние разошлось с игровым. Для HOLD правда - это зажатая клавиша, её не трогаем
        """
        if self._settings.sit.hold_or_press != HoldOrPress.PRESS or self._sit == is_sitting:
            return False
        self._sit = is_sitting
        return True

    @property
    def current_lean(self) -> str | None:
        return self._current_lean

    @property
    def is_sitting(self) -> bool:
        return self._sit
