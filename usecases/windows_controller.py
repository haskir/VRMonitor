from loguru import logger
from pygetwindow import getAllWindows, getActiveWindow, Win32Window

from usecases.singleton import Singleton

from consts import TEST_CAMERA_TITLE as TITLE


class WindowsController(Singleton):
    def __init__(self):
        self._targets = {"PUBG"}
        self._is_all_targets = False
        self._current = ""

    def update_current(self):
        self._current = getActiveWindow().title

    @property
    def is_target_active(self) -> bool:
        if self._is_all_targets:
            return True
        for target in self._targets:
            if target in self._current:
                return True
        return False

    @property
    def is_all_targets(self) -> bool:
        return self._is_all_targets

    @is_all_targets.setter
    def is_all_targets(self, value: bool):
        self._is_all_targets = value
