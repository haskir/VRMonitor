from .pose import Stance

__all__ = ["StanceTracker"]


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
