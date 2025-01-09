from loguru import logger
from pygetwindow import getAllWindows, getActiveWindow, Win32Window

from usecases.singleton import Singleton


class CustomWin32Window(Win32Window):
    def __init__(self, window: Win32Window):
        super().__init__(window._hWnd)

    def __hash__(self):
        return hash(self._hWnd)

    @property
    def hWnd(self) -> int:
        return self._hWnd


class WindowsProvider(Singleton):
    def __init__(self):
        self._targets = dict()
        self._is_all_targets = False

    @classmethod
    def all_windows(cls) -> list[CustomWin32Window]:
        # Перебираем окна и создаем экземпляры CustomWin32Window вместо Win32Window
        return [CustomWin32Window(window) for window in getAllWindows() if window.title]

    @property
    def is_target_active(self) -> bool:
        return self.is_all_targets or self.getActiveWindow.hWnd in self._targets

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