from dataclasses import dataclass
from enum import StrEnum

import cv2
import numpy as np

__all__ = [
    "Region",
    "Stance",
    "StanceDetector",
    "StanceTracker",
    "classify_stance",
    "icon_region",
]

# HUD PUBG масштабируется по высоте экрана и центрирован по горизонтали.
# Все размеры ниже - в пикселях при высоте 1440, иконка позы стоит слева от полосы здоровья
_BASE_HEIGHT = 1440
_REGION_LEFT = -370  # от центра экрана
_REGION_RIGHT = -278  # полоса здоровья начинается на -275, её белая часть не должна попадать в область
_REGION_TOP = 150  # от нижнего края экрана
_REGION_BOTTOM = 50

# Высота силуэта при 1440: стоя ~57, присед ~39, лёжа ~22
_PRONE_MAX_HEIGHT = 30
_CROUCH_MAX_HEIGHT = 48
_MIN_HEIGHT = 15
_MAX_HEIGHT = 68

# Иконка почти белая и бесцветная; фон - что угодно, поэтому порог яркости считается от фона
_MIN_ICON_VALUE = 210
_ICON_CONTRAST = 20
_MAX_ICON_SATURATION = 30


class Stance(StrEnum):
    STAND = "stand"
    CROUCH = "crouch"
    PRONE = "prone"


@dataclass(frozen=True, slots=True)
class Region:
    x: int
    y: int
    width: int
    height: int


def icon_region(width: int, height: int) -> Region:
    """Область поиска иконки позы внутри кадра игры размером width x height"""
    scale = height / _BASE_HEIGHT
    left = int(width / 2 + _REGION_LEFT * scale)
    right = int(width / 2 + _REGION_RIGHT * scale)
    top = int(height - _REGION_TOP * scale)
    bottom = int(height - _REGION_BOTTOM * scale)
    return Region(x=left, y=top, width=right - left, height=bottom - top)


def classify_stance(image: np.ndarray, scale: float) -> Stance | None:
    """
    Определяет позу по BGR-вырезке области иконки; scale - высота экрана / 1440.
    Возвращает None, если уверенно найти силуэт не удалось (HUD скрыт, слишком светлый фон и т.п.)
    """
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    saturation, value = hsv[..., 1], hsv[..., 2]

    # Иконка занимает малую часть области, так что медиана - это яркость фона
    threshold = max(_MIN_ICON_VALUE, int(np.median(value)) + _ICON_CONTRAST)
    if threshold > 245:
        return None  # Фон почти белый - иконку от него не отличить
    mask = ((value >= threshold) & (saturation <= _MAX_ICON_SATURATION)).astype(np.uint8)

    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    if count < 2:
        return None
    index = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
    x, y, w, h, area = (int(v) for v in stats[index])

    # Силуэт, обрезанный краем области, - скорее всего яркий фон, а не иконка
    if x == 0 or y == 0 or x + w == mask.shape[1] or y + h == mask.shape[0]:
        return None
    fill = area / (w * h)
    if not 0.2 <= fill <= 0.55:
        return None

    height = h / scale
    ratio = h / w
    if not _MIN_HEIGHT <= height <= _MAX_HEIGHT:
        return None
    if height < _PRONE_MAX_HEIGHT and ratio < 0.7:
        return Stance.PRONE
    if height <= _CROUCH_MAX_HEIGHT and 0.8 <= ratio <= 1.45:
        return Stance.CROUCH
    if height > _CROUCH_MAX_HEIGHT and ratio > 1.3:
        return Stance.STAND
    return None  # Высота и пропорции противоречат друг другу


class StanceTracker:
    """
    Сглаживает показания: поза меняется после нескольких одинаковых замеров подряд,
    а пропавшая иконка (открыт инвентарь, карта) сбрасывает позу только через некоторое время.
    После нашего нажатия замеры какое-то время игнорируются: игра ещё проигрывает анимацию смены позы
    """

    def __init__(self, confirmations: int = 2, forget_after: int = 8):
        self._confirmations = confirmations
        self._forget_after = forget_after
        self._candidate: Stance | None = None
        self._candidate_count: int = 0
        self._unknown_count: int = 0
        self._ignore_until: float = 0.0
        self.stance: Stance | None = None
        # Поза подтверждена замерами, снятыми уже после последнего нажатия - ей можно верить
        self.is_settled: bool = False

    def ignore_until(self, timestamp: float):
        """Не учитывать замеры, снятые раньше timestamp (time.monotonic)"""
        self._ignore_until = timestamp
        self._candidate = None
        self._candidate_count = 0
        self.is_settled = False

    def update(self, reading: Stance | None, timestamp: float) -> bool:
        """
        Учитывает замер, снятый в момент timestamp (time.monotonic);
        возвращает True, если подтверждённая поза изменилась
        """
        if timestamp < self._ignore_until:
            return False
        if reading is None:
            self._unknown_count += 1
            if self.stance is not None and self._unknown_count >= self._forget_after:
                self.stance = None
                self.is_settled = False
                return True
            return False

        self._unknown_count = 0
        if reading == self._candidate:
            self._candidate_count += 1
        else:
            self._candidate = reading
            self._candidate_count = 1
        if self._candidate_count < self._confirmations:
            return False
        self.is_settled = True
        if reading == self.stance:
            return False
        self.stance = reading
        return True

    def reset(self) -> bool:
        changed = self.stance is not None
        self._candidate = None
        self._candidate_count = 0
        self._unknown_count = 0
        self.stance = None
        self.is_settled = False
        return changed


class StanceDetector:
    """Снимает область иконки с экрана и определяет позу персонажа"""

    def __init__(self):
        self._sct = None  # mss держит контекст устройства потока, создаём лениво в потоке вызова

    def detect(self, screen_rect: tuple[int, int, int, int]) -> Stance | None:
        """screen_rect - клиентская область окна игры на экране: x, y, ширина, высота"""
        x, y, width, height = screen_rect
        if width <= 0 or height <= 0:
            return None
        region = icon_region(width, height)
        if self._sct is None:
            import mss

            self._sct = mss.MSS()
        shot = self._sct.grab(
            {"left": x + region.x, "top": y + region.y, "width": region.width, "height": region.height}
        )
        image = cv2.cvtColor(np.asarray(shot), cv2.COLOR_BGRA2BGR)
        return classify_stance(image, height / _BASE_HEIGHT)
