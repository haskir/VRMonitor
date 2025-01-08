import pygetwindow as gw


class WindowsProvider:
    def __init__(self):
        self._target = None

    @classmethod
    def all_windows(cls) -> dict[str, gw.Win32Window]:
        return {w._hWnd: w for w in gw.getAllWindows() if w.title}

    @property
    def is_target_active(self) -> bool:
        if not self._target:
            return True
        window = gw.getActiveWindow()
        if not window:
            return False
        return gw.getActiveWindow().title == self._target

    def set_target(self, new_target: str | None):
        self._target = new_target
