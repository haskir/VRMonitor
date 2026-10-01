import time

import pydirectinput

__all__ = ["DirectInputKeySender"]

# Отключаем искусственные задержки pydirectinput, чтобы не тормозить цикл обработки камеры
pydirectinput.PAUSE = 0.0
pydirectinput.FAILSAFE = False  # type: ignore

# Играм на DirectX нужна микро-задержка, чтобы заметить "клик" (иначе он слишком быстрый)
TAP_SECONDS = 0.015


class DirectInputKeySender:
    """Нажатия через DirectInput-скан-коды: их видят игры, игнорирующие виртуальные клавиши"""

    def key_down(self, button: str):
        pydirectinput.keyDown(button.lower())

    def key_up(self, button: str):
        pydirectinput.keyUp(button.lower())

    def tap(self, button: str):
        pydirectinput.keyDown(button.lower())
        time.sleep(TAP_SECONDS)
        pydirectinput.keyUp(button.lower())
