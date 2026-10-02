from collections.abc import Callable
from dataclasses import fields
from typing import Any

from loguru import logger

from domain.camera import CameraInfo
from domain.settings import AppSettings

from .events import Event
from .head_tracking import HeadTracking, LiveHead
from .input_controller import InputController
from .ports import CameraCatalog, CameraRuntime, SettingsRepository

__all__ = ["App"]


class App:
    """
    Точка входа для UI: держит настройки, применяет каждое изменение к нужной части приложения
    и сохраняет их. UI не обращается к контроллерам напрямую
    """

    def __init__(
        self,
        settings_repository: SettingsRepository,
        camera_catalog: CameraCatalog,
        camera: CameraRuntime,
        tracking: HeadTracking,
        input_controller: InputController,
    ):
        self._repository = settings_repository
        self._catalog = camera_catalog
        self._camera = camera
        self._tracking = tracking
        self._input = input_controller
        self._is_running = False
        self._dirty = False

        # События испускаются из разных потоков, UI сам переправляет их в свой (см. ui/bridge.py)
        self.game_active_changed = input_controller.game_active_changed
        self.stance_changed = input_controller.stance_changed
        self.calibrated = tracking.calibrated
        self.virtual_cam_failed = camera.virtual_cam_failed
        self.preview_frame = camera.preview_frame
        self.settings_changed: Event[AppSettings] = Event()

        self._appliers: dict[str, Callable[[Any], None]] = {
            "angle_threshold": tracking.set_angle_threshold,
            "sit_enabled": tracking.set_sit_enabled,
            "sit_y": tracking.set_sit_threshold,
            "auto_calibrate": tracking.set_auto_calibrate,
            "visualize": camera.set_overlay,
            "only_in_game": input_controller.set_only_in_game,
            "detect_stance": input_controller.set_detect_stance,
            "virtual_cam": camera.set_virtual_cam,
            "virtual_cam_mesh": camera.set_virtual_cam_mesh,
            "camera_index": self._apply_camera_index,
            "camera_mode": camera.set_mode,
            "bindings": input_controller.set_bindings,
        }
        missing = {f.name for f in fields(AppSettings)} - self._appliers.keys()
        assert not missing, f"Настройки без обработчика: {missing}"

        self.settings: AppSettings = settings_repository.load()
        for name, apply in self._appliers.items():
            apply(getattr(self.settings, name))

    def _apply_camera_index(self, index: int | None):
        if index is not None:
            self._camera.set_camera(index)

    @property
    def is_game_active(self) -> bool:
        return self._input.is_game_active

    @property
    def stance(self):
        return self._input.stance

    @property
    def is_running(self) -> bool:
        return self._is_running

    @property
    def is_camera_blank(self) -> bool:
        return self._is_running and self._camera.is_blank

    def live_head(self) -> LiveHead:
        """Где сейчас голова - для живых подсказок рядом с порогами"""
        return self._tracking.live()

    def update(self, **changes: Any):
        """Меняет настройки, сразу применяет их и помечает для сохранения"""
        changed = False
        for name, value in changes.items():
            if name not in self._appliers:
                raise AttributeError(f"Неизвестная настройка {name}")
            if getattr(self.settings, name) == value:
                continue
            setattr(self.settings, name, value)
            self._appliers[name](value)
            changed = True
        if changed:
            self._dirty = True
            self.settings_changed.emit(self.settings)

    def save(self):
        if self._dirty:
            self._repository.save(self.settings)
            self._dirty = False

    def list_cameras(self) -> list[CameraInfo]:
        return self._catalog.list_cameras()

    def set_running(self, running: bool):
        logger.info(f"Распознавание {'включено' if running else 'выключено'}")
        self._is_running = running
        self._input.set_running(running)
        if running:
            self._camera.start()
        else:
            self._camera.stop()

    def set_preview_visible(self, visible: bool):
        self._camera.set_preview_visible(visible)

    def poll(self):
        """Периодическая проверка активного окна и позы персонажа (из потока UI)"""
        self._input.poll()

    def shutdown(self):
        self.save()
        self._camera.stop(wait=True)
        self._input.release_held()
