from collections.abc import Callable

__all__ = ["Event"]


class Event[T]:
    """
    Простое событие без зависимостей от GUI. Обработчики вызываются в потоке, который испустил событие,
    поэтому UI переправляет их в свой поток сам (см. ui/bridge.py)
    """

    def __init__(self):
        self._handlers: list[Callable[[T], None]] = []

    def connect(self, handler: Callable[[T], None]):
        self._handlers.append(handler)

    def emit(self, value: T):
        for handler in list(self._handlers):
            handler(value)
