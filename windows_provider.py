import pygetwindow as gw


class WindowsProvider:
    def __init__(self):
        self._target = None

    @classmethod
    def all_windows(cls) -> dict[int, str]:
        return {-1: "Любое окно"} | {i: window.title for i, window in enumerate(gw.getAllWindows()) if window.title}

    @property
    def is_target_active(self) -> bool:
        if not self._target or self._target == "Любое окно":
            return True
        return gw.getActiveWindow().title == self._target

    def set_target(self, new_target: str | None):
        self._target = new_target
