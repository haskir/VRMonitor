"""Интерфейсы внешнего мира, которые нужны приложению. Реализации - в infrastructure"""

from typing import Protocol

from domain.camera import CameraInfo, CameraMode
from domain.pose import Stance
from domain.settings import AppSettings

from .events import Event

__all__ = [
    "CameraCatalog",
    "CameraRuntime",
    "GameWindow",
    "KeySender",
    "ScreenRect",
    "SettingsRepository",
    "StanceProbe",
]

type ScreenRect = tuple[int, int, int, int]  # x, y, ширина, высота в координатах экрана


class KeySender(Protocol):
    def key_down(self, button: str) -> None: ...

    def key_up(self, button: str) -> None: ...

    def tap(self, button: str) -> None:
        """Короткое нажатие и отпускание"""
        ...


class GameWindow(Protocol):
    def is_game_active(self) -> bool:
        """Игра на переднем плане"""
        ...

    def foreground_rect(self) -> ScreenRect | None:
        """Клиентская область активного окна"""
        ...


class StanceProbe(Protocol):
    def detect(self, rect: ScreenRect) -> Stance | None:
        """Поза персонажа по HUD игры в области rect; None - определить не удалось"""
        ...


class SettingsRepository(Protocol):
    def load(self) -> AppSettings: ...

    def save(self, settings: AppSettings) -> None: ...


class CameraCatalog(Protocol):
    def list_cameras(self) -> list[CameraInfo]: ...


class CameraRuntime(Protocol):
    """Захват камеры, распознавание позы головы и вывод картинки (предпросмотр, OBS)"""

    virtual_cam_failed: Event[str]  # Испускается из потока камеры

    @property
    def is_blank(self) -> bool:
        """Камера отдаёт сплошной чёрный кадр (занята другой программой или закрыта шторкой)"""
        ...

    def start(self) -> None: ...

    def stop(self, wait: bool = False) -> None: ...

    def set_camera(self, index: int) -> None: ...

    def set_mode(self, mode: CameraMode | None) -> None: ...

    def set_preview_visible(self, visible: bool) -> None: ...

    def set_overlay(self, enabled: bool) -> None: ...

    def set_virtual_cam(self, enabled: bool) -> None: ...

    def set_virtual_cam_mesh(self, enabled: bool) -> None: ...
