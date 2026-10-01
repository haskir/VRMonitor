import numpy as np

__all__ = ["BlankFrameDetector"]

BLANK_MAX_VALUE = 16  # Ярче этого пикселей нет - кадр сплошной чёрный
BLANK_SECONDS = 1.5  # Сколько чёрных кадров подряд терпим (камера может стартовать с тёмных кадров)
_STEP = 8  # Проверяем каждый 8-й пиксель по обеим осям - этого хватает и почти бесплатно


class BlankFrameDetector:
    """
    Замечает, что камера отдаёт сплошной чёрный кадр. Так бывает, когда её заняла другая программа
    (например, OBS, где камера добавлена источником) или объектив закрыт шторкой
    """

    def __init__(self, blank_seconds: float = BLANK_SECONDS):
        self._blank_seconds = blank_seconds
        self._blank_since: float | None = None
        self.is_blank = False

    def update(self, frame: np.ndarray, now: float) -> bool:
        """Учитывает кадр; возвращает True, если состояние изменилось"""
        if frame[::_STEP, ::_STEP].max() > BLANK_MAX_VALUE:
            self._blank_since = None
            return self._set(False)
        if self._blank_since is None:
            self._blank_since = now
        return self._set(now - self._blank_since >= self._blank_seconds)

    def reset(self):
        self._blank_since = None
        self.is_blank = False

    def _set(self, is_blank: bool) -> bool:
        changed = is_blank != self.is_blank
        self.is_blank = is_blank
        return changed
