import time
from collections.abc import Callable
from dataclasses import dataclass

from loguru import logger

from domain.gestures import LeanDetector, SitDetector
from domain.pose import HeadPose
from domain.settings import DEFAULT_ANGLE_THRESHOLD

from .events import Event
from .input_controller import InputController

__all__ = ["POSE_STALE_SECONDS", "HeadTracking", "LiveHead", "TrackingOverlay"]

POSE_STALE_SECONDS = 1.0  # Лица нет на камере дольше - считаем, что оно потеряно


@dataclass(frozen=True, slots=True)
class TrackingOverlay:
    """Что показать поверх предпросмотра камеры"""

    angle_threshold: float
    sit_enabled: bool
    sit_threshold: int
    base_y: int | None


@dataclass(frozen=True, slots=True)
class LiveHead:
    """Текущее положение головы для подсказок в интерфейсе"""

    pose: HeadPose | None  # None - лица нет на камере
    base_y: int | None  # Откалиброванный верх головы


class HeadTracking:
    """Поза головы с камеры -> наклоны и присед -> InputController. Вызывается из потока камеры"""

    def __init__(self, input_controller: InputController, clock: Callable[[], float] = time.monotonic):
        self._input = input_controller
        self._clock = clock
        self._lean = LeanDetector(DEFAULT_ANGLE_THRESHOLD)
        self._sit = SitDetector()
        self._sit_enabled = True
        self._last_pose: tuple[HeadPose, float] | None = None  # Поза и время, когда её увидели
        # Испускается из потока камеры
        self.calibrated: Event[int] = Event()

    def set_angle_threshold(self, threshold: float):
        self._lean.threshold = threshold

    def set_sit_enabled(self, enabled: bool):
        self._sit_enabled = enabled
        self._input.set_sit_enabled(enabled)

    def set_sit_threshold(self, threshold: int):
        if abs(threshold) != self._sit.threshold:
            logger.info(f"Установка порога Y: {abs(threshold)}")
        self._sit.set_threshold(threshold)

    def set_auto_calibrate(self, enabled: bool):
        logger.info(f"Авто-калибровка: {'вкл' if enabled else 'выкл'}")
        self._sit.set_auto_calibrate(enabled)

    def overlay(self) -> TrackingOverlay:
        return TrackingOverlay(
            angle_threshold=self._lean.threshold,
            sit_enabled=self._sit_enabled,
            sit_threshold=self._sit.threshold,
            base_y=self._sit.base_y,
        )

    def live(self) -> LiveHead:
        last = self._last_pose
        fresh = last is not None and self._clock() - last[1] <= POSE_STALE_SECONDS
        return LiveHead(pose=last[0] if fresh else None, base_y=self._sit.base_y)

    def on_pose(self, pose: HeadPose):
        now = self._clock()
        self._last_pose = (pose, now)
        if (lean := self._lean.update(pose.tilt)) is not None:
            self._input.set_lean(lean)

        if not self._sit_enabled:
            return
        update = self._sit.update(pose.y, now)
        if update.calibrated_threshold is not None:
            logger.info(f"Авто-калибровка: верх Y={self._sit.base_y}, порог приседа Y={update.calibrated_threshold}")
            self.calibrated.emit(update.calibrated_threshold)
        if update.sitting is not None:
            self._input.set_sitting(update.sitting)
