from pygetwindow import getActiveWindow

from consts import ON_ALL_WINDOWS


class WindowsController:
    def __init__(self):
        self._targets = {"PUBG"}
        self._is_all_targets = ON_ALL_WINDOWS
        self._current = ""

    def update_current(self):
        self._current = getActiveWindow().title

    @property
    def is_target_active(self) -> bool:
        if self._is_all_targets:
            return True
        return any(target in self._current for target in self._targets)

    @property
    def is_all_targets(self) -> bool:
        return self._is_all_targets

    @is_all_targets.setter
    def is_all_targets(self, value: bool):
        self._is_all_targets = value
