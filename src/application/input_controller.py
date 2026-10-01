import threading
import time
from collections.abc import Callable

from loguru import logger

from domain.bindings import GameBindings
from domain.pose import Lean, Stance
from domain.stance_tracker import StanceTracker

from .events import Event
from .game_keys import GameKeys
from .ports import GameWindow, StanceProbe

__all__ = ["STANCE_SETTLE_SECONDS", "InputController"]

STANCE_SETTLE_SECONDS = 0.7  # Сколько после нажатия приседа не верить иконке позы - идёт анимация


class InputController:
    """
    Сводит желаемое состояние (что делает голова на камере) с фактическим (что нажато в игре).
    Клавиши жмутся, только пока игра на переднем плане (если не включён режим "в любом окне").
    Поза персонажа из HUD игры - источник истины для приседа: лёжа присед не жмётся,
    а если игрок сам сменил позу, состояние принимается из игры
    """

    def __init__(
        self,
        keys: GameKeys,
        window: GameWindow,
        stance_probe: StanceProbe,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._keys = keys
        self._window = window
        self._stance_probe = stance_probe
        self._clock = clock

        self.game_active_changed: Event[bool] = Event()
        self.stance_changed: Event[Stance | None] = Event()

        self._only_in_game = True
        self._sit_enabled = True
        self._detect_stance = True
        self._is_running = False  # Идёт ли распознавание с камеры

        # Что делает голова прямо сейчас; на клавиатуру применяется, только пока активна игра
        self._desired_lean = Lean.NONE
        self._desired_sit: bool | None = None  # None - ещё неизвестно
        # Клавиши жмутся и из потока камеры, и из таймера опроса окна
        self._lock = threading.RLock()
        self._target_active = False
        self._game_active = False
        self._stance_tracker = StanceTracker()

    # --- Состояние для UI ---

    @property
    def is_game_active(self) -> bool:
        return self._game_active

    @property
    def stance(self) -> Stance | None:
        return self._stance_tracker.stance

    # --- Настройки ---

    def set_bindings(self, bindings: GameBindings):
        with self._lock:
            self._keys.bindings = bindings

    def set_only_in_game(self, only_in_game: bool):
        logger.info("Клавиши нажимаются только в игре" if only_in_game else "Клавиши нажимаются в любом окне")
        self._only_in_game = only_in_game
        self._sync()

    def set_sit_enabled(self, enabled: bool):
        logger.info("Включение приседаний" if enabled else "Выключение приседаний")
        self._sit_enabled = enabled

    def set_detect_stance(self, detect_stance: bool):
        logger.info("Поза в игре учитывается" if detect_stance else "Поза в игре не учитывается")
        self._detect_stance = detect_stance
        self._update_stance()

    def set_running(self, running: bool):
        self._is_running = running
        if not running:
            # Распознавание выключено - голова "в нейтрали", отпускаем наклон
            self._desired_lean = Lean.NONE
            self._sync()

    # --- Желаемое состояние (вызывается из потока камеры) ---

    def set_lean(self, lean: Lean):
        self._desired_lean = lean
        self._sync()

    def set_sitting(self, sitting: bool):
        self._desired_sit = sitting
        self._sync()

    # --- Периодический опрос (вызывается из потока UI по таймеру) ---

    def poll(self):
        game_active = self._window.is_game_active()
        if game_active != self._game_active:
            self._game_active = game_active
            logger.info(f"Игра {'на переднем плане' if game_active else 'не в фокусе'}")
            self.game_active_changed.emit(game_active)
        self._update_stance()
        self._sync()

    def release_held(self):
        """Отпускает зажатое при выходе. Переключатели не трогаем: повторное нажатие ушло бы в другое окно"""
        with self._lock:
            self._keys.release_held()

    def _update_stance(self):
        """Снимает иконку позы с HUD, пока игра на переднем плане и детекция включена"""
        tracker = self._stance_tracker
        if not (self._detect_stance and self._is_running and self._game_active):
            with self._lock:
                changed = tracker.reset()
            if changed:
                self._on_stance_changed(tracker.stance)
            return

        reading = None
        # Время снимка берём до него: нажатие из потока камеры могло случиться, пока снимали экран
        timestamp = self._clock()
        rect = self._window.foreground_rect()
        if rect:
            try:
                reading = self._stance_probe.detect(rect)
            except Exception as e:
                logger.error(f"Не удалось определить позу персонажа: {e}")
        with self._lock:
            changed = tracker.update(reading, timestamp)
            # Игра - источник истины: если игрок сам сменил позу, принимаем её, а _sync приведёт к камере
            if (
                tracker.is_settled
                and tracker.stance in (Stance.STAND, Stance.CROUCH)
                and self._keys.assume_sitting(tracker.stance == Stance.CROUCH)
            ):
                logger.info(f"Поза в игре разошлась с нашей, принимаю игровую: {tracker.stance}")
        if changed:
            self._on_stance_changed(tracker.stance)

    def _on_stance_changed(self, stance: Stance | None):
        logger.info(f"Поза персонажа: {stance or 'неизвестна'}")
        self.stance_changed.emit(stance)

    def _sync(self):
        """Приводит нажатые клавиши к желаемому состоянию с учётом активного окна"""
        with self._lock:
            keys = self._keys
            if self._only_in_game and not self._window.is_game_active():
                if self._target_active:
                    # Ушли из игры - отпускаем зажатые клавиши, чтобы они не "залипли" в других окнах
                    keys.release_held()
                self._target_active = False
                return
            self._target_active = True

            keys.set_lean(self._desired_lean)

            is_prone = self._stance_tracker.stance == Stance.PRONE
            if (
                self._sit_enabled
                and not is_prone
                and self._desired_sit is not None
                and self._desired_sit != keys.is_sitting
            ):
                keys.set_sitting(self._desired_sit)
                # Пока идёт анимация, иконка показывает старую позу - не принимаем её за истину
                self._stance_tracker.ignore_until(self._clock() + STANCE_SETTLE_SECONDS)
