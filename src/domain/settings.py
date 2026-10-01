from dataclasses import dataclass, field

from .bindings import GameBindings
from .camera import CameraMode

__all__ = ["DEFAULT_ANGLE_THRESHOLD", "AppSettings"]

DEFAULT_ANGLE_THRESHOLD = 20


@dataclass
class AppSettings:
    angle_threshold: int = DEFAULT_ANGLE_THRESHOLD  # Наклон головы в градусах, после которого жмётся наклон
    sit_enabled: bool = True
    sit_y: int = 0  # Порог приседа (в единицах Y_SCALE), 0 - не задан
    auto_calibrate: bool = False
    visualize: bool = False
    only_in_game: bool = True  # Нажимать клавиши только когда игра на переднем плане
    detect_stance: bool = True  # Сверять присед с позой персонажа по иконке в HUD игры
    virtual_cam: bool = False  # Вывод картинки в виртуальную камеру OBS
    virtual_cam_mesh: bool = True
    camera_index: int | None = None
    camera_mode: CameraMode | None = None  # None - режим камеры по умолчанию
    bindings: GameBindings = field(default_factory=GameBindings.default)
