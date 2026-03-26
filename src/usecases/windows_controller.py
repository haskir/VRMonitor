from collections.abc import Sequence

from pygetwindow import getActiveWindow

from consts import ON_ALL_WINDOWS

__all__ = ["WindowsController"]


class WindowsController:
    """Контролирует, на каких окнах будет работать, а на какие нет"""

    def __init__(self, targets: Sequence[str]):
        self._targets = set(targets if targets else ["PUBG"])
        self._is_all_targets: bool = ON_ALL_WINDOWS
        self._current: str = ""

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
