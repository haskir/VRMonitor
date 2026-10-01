from dataclasses import dataclass

from .pose import Lean

__all__ = [
    "CALIBRATION_SECONDS",
    "CALIBRATION_TOLERANCE",
    "DEFAULT_SIT_DEPTH",
    "LeanDetector",
    "SitDetector",
    "SitUpdate",
]

# Авто-калибровка верхнего положения головы
CALIBRATION_SECONDS = 20  # Сколько держать голову неподвижно, чтобы принять её Y за верхнее положение
CALIBRATION_TOLERANCE = 15  # Допустимое дрожание головы по Y (в единицах Y_SCALE)
DEFAULT_SIT_DEPTH = 80  # Глубина приседа по умолчанию (в единицах Y ниже верхнего положения)


class LeanDetector:
    """Наклон головы в градусах -> наклон персонажа"""

    def __init__(self, threshold: float):
        self.threshold = threshold
        self._lean = Lean.NONE

    def update(self, tilt: float) -> Lean | None:
        """Возвращает новый наклон, если он изменился"""
        lean = Lean.NONE
        if abs(tilt) > self.threshold:
            lean = Lean.LEFT if tilt > 0 else Lean.RIGHT
        if lean == self._lean:
            return None
        self._lean = lean
        return lean


@dataclass(frozen=True, slots=True)
class SitUpdate:
    sitting: bool | None = None  # Новое состояние приседа, если изменилось
    calibrated_threshold: int | None = None  # Новый порог после авто-калибровки


class SitDetector:
    """
    Высота головы -> присед. Голова ниже порога - сидим.
    Авто-калибровка: если голова долго неподвижна в верхнем положении, оно становится базой,
    а порог сдвигается так, чтобы глубина приседа (порог - база) сохранилась
    """

    def __init__(
        self,
        threshold: int = 0,
        auto_calibrate: bool = False,
        calibration_seconds: float = CALIBRATION_SECONDS,
        calibration_tolerance: float = CALIBRATION_TOLERANCE,
        sit_depth: int = DEFAULT_SIT_DEPTH,
    ):
        self._threshold = abs(threshold)  # 0 - порог не задан, приседания не отслеживаются
        self._sitting: bool | None = None
        self._auto_calibrate = auto_calibrate
        self._calibration_seconds = calibration_seconds
        self._calibration_tolerance = calibration_tolerance
        self._sit_depth = sit_depth
        self._base_y: int | None = None
        self._anchor_y: float | None = None
        self._anchor_time: float = 0.0

    @property
    def threshold(self) -> int:
        return self._threshold

    @property
    def base_y(self) -> int | None:
        """Откалиброванное верхнее положение головы"""
        return self._base_y

    def set_threshold(self, threshold: int):
        threshold = abs(threshold)
        if threshold == self._threshold:
            return
        self._threshold = threshold
        # Ручная правка порога при известной базе задаёт глубину приседа
        if self._base_y is not None and threshold > self._base_y:
            self._sit_depth = threshold - self._base_y

    def set_auto_calibrate(self, enabled: bool):
        self._auto_calibrate = enabled
        self._anchor_y = None

    def update(self, head_y: float, now: float) -> SitUpdate:
        calibrated = self._calibrate(head_y, now)
        if not self._threshold:
            return SitUpdate(calibrated_threshold=calibrated)
        sitting = head_y > self._threshold
        if sitting == self._sitting:
            return SitUpdate(calibrated_threshold=calibrated)
        self._sitting = sitting
        return SitUpdate(sitting=sitting, calibrated_threshold=calibrated)

    def _calibrate(self, head_y: float, now: float) -> int | None:
        if not self._auto_calibrate:
            return None
        # Калибруемся только стоя, иначе долгое сидение станет новым "верхом"
        if self._threshold and head_y > self._threshold:
            self._anchor_y = None
            return None

        if self._anchor_y is None or abs(head_y - self._anchor_y) > self._calibration_tolerance:
            self._anchor_y = head_y
            self._anchor_time = now
            return None
        if now - self._anchor_time < self._calibration_seconds:
            return None

        self._anchor_time = now
        base_y = int(self._anchor_y)
        if self._base_y is None and self._threshold > base_y:
            # Первая калибровка: сохраняем глубину, которую пользователь выставил вручную
            self._sit_depth = self._threshold - base_y
        self._base_y = base_y
        threshold = base_y + self._sit_depth
        if threshold == self._threshold:
            return None
        self._threshold = threshold
        return threshold
