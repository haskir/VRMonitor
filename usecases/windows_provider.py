from loguru import logger
from pygetwindow import getAllWindows, getActiveWindow, Win32Window

from usecases.singleton import Singleton

from consts import TEST_CAMERA_TITLE as TITLE


class CustomWin32Window(Win32Window):
    def __init__(self, window: Win32Window):
        super().__init__(window._hWnd)

    def __hash__(self):
        return hash(self._hWnd)

    @property
    def hWnd(self) -> int:
        try:
            return self._hWnd
        except AttributeError:
            return -1


class WindowsProvider(Singleton):
    def __init__(self):
        self._targets = dict()
        self._is_all_targets = False

    @classmethod
    def all_windows(cls) -> list[CustomWin32Window]:
        # Перебираем окна и создаем экземпляры CustomWin32Window вместо Win32Window
        return [CustomWin32Window(window) for window in getAllWindows() if window.title and TITLE not in window.title]

    @property
    def is_target_active(self) -> bool:
        if self._is_all_targets:
            return True
        for hWnd, window in self._targets.items():
            try:
                if window.hWnd == self.getActiveWindow.hWnd:
                    return True
            except (AttributeError, ValueError):
                logger.debug(f"Попытка удаления несуществующего окна [{window.hWnd}]")
                self.remove_window(window)

        return False

    @property
    def getActiveWindow(self) -> CustomWin32Window:
        return CustomWin32Window(getActiveWindow())

    def add_window(self, window: CustomWin32Window):
        self._targets[window.hWnd] = window

    def remove_window(self, window: CustomWin32Window):
        try:
            self._targets.pop(window.hWnd)
        except KeyError:
            logger.debug(f"Попытка удаления несуществующего окна [{window.hWnd}]")

    @property
    def is_all_targets(self) -> bool:
        return self._is_all_targets

    @is_all_targets.setter
    def is_all_targets(self, value: bool):
        self._is_all_targets = value