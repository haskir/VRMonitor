from dataclasses import dataclass
from enum import StrEnum

__all__ = ["Y_SCALE", "HeadPose", "Lean", "Stance"]

# Y головы считается в долях высоты кадра * Y_SCALE, чтобы порог не зависел от разрешения камеры
Y_SCALE = 500


class Lean(StrEnum):
    NONE = "none"
    LEFT = "left"
    RIGHT = "right"


class Stance(StrEnum):
    """Поза персонажа в игре"""

    STAND = "stand"
    CROUCH = "crouch"
    PRONE = "prone"


@dataclass(frozen=True, slots=True)
class HeadPose:
    tilt: float  # Наклон головы в градусах, > 0 - влево
    y: float  # Высота головы в кадре в единицах Y_SCALE, больше - ниже
