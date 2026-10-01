import ctypes
from collections.abc import Sequence
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import PureWindowsPath

from consts import TARGET_PROCESSES, TARGET_TITLES

__all__ = ["ForegroundWindow", "WindowsController"]

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


@dataclass(frozen=True, slots=True)
class ForegroundWindow:
    title: str
    process: str  # Имя exe, пустое если процесс не удалось открыть


def _process_name(pid: int) -> str:
    # LIMITED_INFORMATION хватает даже для процессов под защитой античита (BattlEye у PUBG)
    handle = _kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        buffer = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(len(buffer))
        if not _kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return ""
        return PureWindowsPath(buffer.value).name
    finally:
        _kernel32.CloseHandle(handle)


class WindowsController:
    """Контролирует, на каких окнах будет работать, а на какие нет"""

    def __init__(
        self,
        target_processes: Sequence[str] = TARGET_PROCESSES,
        target_titles: Sequence[str] = TARGET_TITLES,
    ):
        self._target_processes = {name.lower() for name in target_processes}
        self._target_titles = tuple(target_titles)
        self._is_all_targets: bool = False
        self._process_names: dict[int, str] = {}  # pid -> имя exe, чтобы не открывать процесс каждый раз

    def get_foreground(self) -> ForegroundWindow | None:
        hwnd = _user32.GetForegroundWindow()
        if not hwnd:
            return None
        pid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        title = ctypes.create_unicode_buffer(512)
        _user32.GetWindowTextW(hwnd, title, len(title))
        if pid.value not in self._process_names:
            self._process_names[pid.value] = _process_name(pid.value)
        return ForegroundWindow(title=title.value.strip(), process=self._process_names[pid.value])

    def is_target(self, window: ForegroundWindow | None) -> bool:
        if window is None:
            return False
        if window.process:
            return window.process.lower() in self._target_processes
        # Процесс не открылся - определяем по заголовку
        return any(target in window.title for target in self._target_titles)

    @property
    def is_game_active(self) -> bool:
        """Игра на переднем плане (независимо от режима "на всех окнах"); проверка занимает ~20 мкс"""
        return self.is_target(self.get_foreground())

    @property
    def is_target_active(self) -> bool:
        return self._is_all_targets or self.is_game_active

    @property
    def is_all_targets(self) -> bool:
        return self._is_all_targets

    @is_all_targets.setter
    def is_all_targets(self, value: bool):
        self._is_all_targets = value
