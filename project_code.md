## `application\__init__.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\application\__init__.py`

```python

```

## `application\app.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\application\app.py`

```python
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

```

## `application\events.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\application\events.py`

```python
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

```

## `application\game_keys.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\application\game_keys.py`

```python
from loguru import logger

from domain.bindings import GameBindings, KeyBinding, KeyMode
from domain.pose import Lean

from .ports import KeySender

__all__ = ["GameKeys"]


class GameKeys:
    """Помнит, какие действия сейчас включены в игре, и жмёт клавиши согласно привязкам"""

    def __init__(self, sender: KeySender, bindings: GameBindings | None = None):
        self._sender = sender
        self._bindings = bindings or GameBindings.default()
        self._lean = Lean.NONE
        self._sitting = False

    @property
    def bindings(self) -> GameBindings:
        return self._bindings

    @bindings.setter
    def bindings(self, bindings: GameBindings):
        self._bindings = bindings

    @property
    def lean(self) -> Lean:
        return self._lean

    @property
    def is_sitting(self) -> bool:
        return self._sitting

    def _activate(self, binding: KeyBinding):
        logger.debug(f"Включение {binding}")
        if binding.mode == KeyMode.HOLD:
            self._sender.key_down(binding.button)
        else:
            self._sender.tap(binding.button)

    def _deactivate(self, binding: KeyBinding):
        logger.debug(f"Выключение {binding}")
        if binding.mode == KeyMode.HOLD:
            self._sender.key_up(binding.button)
        else:
            self._sender.tap(binding.button)  # Переключатель отменяется повторным нажатием

    def _lean_binding(self, lean: Lean) -> KeyBinding | None:
        return {Lean.LEFT: self._bindings.left, Lean.RIGHT: self._bindings.right}.get(lean)

    def set_lean(self, lean: Lean):
        if lean == self._lean:
            return
        # Сначала отменяем текущий наклон, иначе в игре включатся оба
        if current := self._lean_binding(self._lean):
            self._deactivate(current)
        if target := self._lean_binding(lean):
            self._activate(target)
        self._lean = lean

    def set_sitting(self, sitting: bool):
        if sitting == self._sitting:
            return
        logger.info("Сажусь" if sitting else "Встаю")
        if sitting:
            self._activate(self._bindings.sit)
        else:
            self._deactivate(self._bindings.sit)
        self._sitting = sitting

    def release_held(self):
        """
        Отпускает удерживаемые (HOLD) клавиши, например при уходе из игры.
        Переключатели (PRESS) не трогаем: их состояние хранит игра, а нажатие вне её напечатало бы букву
        """
        lean = self._lean_binding(self._lean)
        if lean and lean.mode == KeyMode.HOLD:
            self._sender.key_up(lean.button)
            self._lean = Lean.NONE
        if self._sitting and self._bindings.sit.mode == KeyMode.HOLD:
            self._sender.key_up(self._bindings.sit.button)
            self._sitting = False

    def assume_sitting(self, sitting: bool) -> bool:
        """
        Принимает состояние приседа, увиденное в игре, без нажатий; возвращает True, если оно изменилось.
        Нужно только для переключателя (PRESS): игрок мог сам нажать присед или встать из положения лёжа,
        и наше состояние разошлось с игровым. Для HOLD правда - это зажатая клавиша, её не трогаем
        """
        if self._bindings.sit.mode != KeyMode.PRESS or self._sitting == sitting:
            return False
        self._sitting = sitting
        return True

```

## `application\head_tracking.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\application\head_tracking.py`

```python
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

```

## `application\input_controller.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\application\input_controller.py`

```python
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

```

## `application\ports.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\application\ports.py`

```python
"""Интерфейсы внешнего мира, которые нужны приложению. Реализации - в infrastructure"""

from typing import Protocol

from domain.camera import CameraInfo, CameraMode
from domain.pose import Stance
from domain.settings import AppSettings

from .events import Event

__all__ = [
    "CameraCatalog",
    "CameraRuntime",
    "GameWindow",
    "KeySender",
    "ScreenRect",
    "SettingsRepository",
    "StanceProbe",
]

type ScreenRect = tuple[int, int, int, int]  # x, y, ширина, высота в координатах экрана


class KeySender(Protocol):
    def key_down(self, button: str) -> None: ...

    def key_up(self, button: str) -> None: ...

    def tap(self, button: str) -> None:
        """Короткое нажатие и отпускание"""
        ...


class GameWindow(Protocol):
    def is_game_active(self) -> bool:
        """Игра на переднем плане"""
        ...

    def foreground_rect(self) -> ScreenRect | None:
        """Клиентская область активного окна"""
        ...


class StanceProbe(Protocol):
    def detect(self, rect: ScreenRect) -> Stance | None:
        """Поза персонажа по HUD игры в области rect; None - определить не удалось"""
        ...


class SettingsRepository(Protocol):
    def load(self) -> AppSettings: ...

    def save(self, settings: AppSettings) -> None: ...


class CameraCatalog(Protocol):
    def list_cameras(self) -> list[CameraInfo]: ...


class CameraRuntime(Protocol):
    """Захват камеры, распознавание позы головы и вывод картинки (предпросмотр, OBS)"""

    virtual_cam_failed: Event[str]  # Испускается из потока камеры

    @property
    def is_blank(self) -> bool:
        """Камера отдаёт сплошной чёрный кадр (занята другой программой или закрыта шторкой)"""
        ...

    def start(self) -> None: ...

    def stop(self, wait: bool = False) -> None: ...

    def set_camera(self, index: int) -> None: ...

    def set_mode(self, mode: CameraMode | None) -> None: ...

    def set_preview_visible(self, visible: bool) -> None: ...

    def set_overlay(self, enabled: bool) -> None: ...

    def set_virtual_cam(self, enabled: bool) -> None: ...

    def set_virtual_cam_mesh(self, enabled: bool) -> None: ...

```

## `consts.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\consts.py`

```python
from pathlib import Path

# Игра, в которую нажимаются клавиши (если не включён режим "в любом окне")
TARGET_GAME_NAME = "PUBG"
TARGET_PROCESSES = ("TslGame.exe",)
TARGET_TITLES = ("PUBG: BATTLEGROUNDS",)  # Запасной вариант, если процесс не удалось открыть
POLL_INTERVAL_MS = 250  # Как часто проверять активное окно и позу персонажа

# Работает и при запуске через `uv run`, и в собранном nuitka-бинаре
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

FACE_LANDMARKER_PATH = STATIC_DIR / "face_landmarker.task"
FACE_LANDMARKER_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
)

```

## `domain\__init__.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\domain\__init__.py`

```python

```

## `domain\bindings.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\domain\bindings.py`

```python
from dataclasses import dataclass, replace
from enum import StrEnum

__all__ = [
    "Action",
    "GameBindings",
    "KeyBinding",
    "KeyMode",
]


class KeyMode(StrEnum):
    HOLD = "hold"  # Клавиша зажата, пока действие активно
    PRESS = "press"  # Клавиша-переключатель: нажатие включает действие, повторное - выключает


class Action(StrEnum):
    LEAN_LEFT = "left"
    LEAN_RIGHT = "right"
    SIT = "sit"


@dataclass(frozen=True, slots=True)
class KeyBinding:
    button: str
    mode: KeyMode

    def __repr__(self):
        return f"{self.button}: {self.mode}"


@dataclass(frozen=True, slots=True)
class GameBindings:
    left: KeyBinding
    right: KeyBinding
    sit: KeyBinding

    @classmethod
    def default(cls) -> "GameBindings":
        return cls(
            left=KeyBinding(button="Q", mode=KeyMode.HOLD),
            right=KeyBinding(button="E", mode=KeyMode.HOLD),
            sit=KeyBinding(button="C", mode=KeyMode.PRESS),
        )

    def get(self, action: Action) -> KeyBinding:
        return getattr(self, action.value)

    def with_binding(self, action: Action, binding: KeyBinding) -> "GameBindings":
        return replace(self, **{action.value: binding})

```

## `domain\camera.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\domain\camera.py`

```python
from dataclasses import dataclass, field

__all__ = ["CameraInfo", "CameraMode"]


@dataclass(frozen=True, slots=True)
class CameraMode:
    width: int
    height: int
    fps: int
    fourcc: str

    def __repr__(self):
        return f"{self.width}x{self.height} @ {self.fps} fps ({self.fourcc})"


@dataclass
class CameraInfo:
    index: int  # Системный индекс камеры (порядок DirectShow)
    name: str
    modes: list[CameraMode] = field(default_factory=list)

    def __repr__(self):
        return f"Устройство {self.index:02d}: {self.name}"

```

## `domain\gestures.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\domain\gestures.py`

```python
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

```

## `domain\pose.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\domain\pose.py`

```python
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

```

## `domain\settings.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\domain\settings.py`

```python
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

```

## `domain\stance_tracker.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\domain\stance_tracker.py`

```python
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

```

## `infrastructure\__init__.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\infrastructure\__init__.py`

```python

```

## `infrastructure\camera\__init__.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\infrastructure\camera\__init__.py`

```python

```

## `infrastructure\camera\blank_frames.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\infrastructure\camera\blank_frames.py`

```python
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

```

## `infrastructure\camera\capture.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\infrastructure\camera\capture.py`

```python
import threading

import cv2
import numpy as np
from loguru import logger

from domain.camera import CameraMode

__all__ = ["CameraCaptureThread"]


class CameraCaptureThread:
    """
    Отдельный поток для постоянного чтения веб-камеры.
    Решает проблему буферизации Windows и убирает задержку в 100-150мс.
    """

    def __init__(self, camera_index: int = 0, mode: CameraMode | None = None):
        # CAP_DSHOW ускоряет захват на Windows
        self.cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        if mode:
            # Порядок важен: DirectShow применяет FOURCC только после размера и fps,
            # иначе молча остаётся на YUY2 (1080p в нём - 5 fps вместо 60)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, mode.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, mode.height)
            self.cap.set(cv2.CAP_PROP_FPS, mode.fps)
            if len(mode.fourcc) == 4:  # RGB24 и подобные задаются не FOURCC, а форматом по умолчанию
                self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc(*mode.fourcc))
        fourcc = int(self.cap.get(cv2.CAP_PROP_FOURCC)).to_bytes(4, "little").decode("ascii", "replace")
        logger.info(
            f"Камера {camera_index}: {int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x"
            f"{int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))} @ {self.cap.get(cv2.CAP_PROP_FPS):.0f} fps ({fourcc})"
        )
        self.fps: float = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.ret, self.frame = self.cap.read()
        self.is_running: bool = True
        self.frame_id: int = 0
        self._new_frame = threading.Condition()
        self.thread: threading.Thread = threading.Thread(target=self._update, daemon=True)

    def start(self):
        self.thread.start()

    def _update(self):
        while self.is_running:
            # Постоянно вычитываем кадры, оставляя только самый свежий
            ret, frame = self.cap.read()
            if ret:
                with self._new_frame:
                    self.ret = ret
                    self.frame = frame
                    self.frame_id += 1
                    self._new_frame.notify_all()

    def wait_for_frame(self, last_frame_id: int, timeout: float = 0.5) -> tuple[bool, np.ndarray, int]:
        """Блокируется до появления кадра новее last_frame_id (без холостого опроса)"""
        with self._new_frame:
            self._new_frame.wait_for(lambda: self.frame_id != last_frame_id or not self.is_running, timeout)
            return self.ret, self.frame, self.frame_id

    def stop(self):
        self.is_running = False
        self.thread.join()
        self.cap.release()

```

## `infrastructure\camera\catalog.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\infrastructure\camera\catalog.py`

```python
import cv2
from loguru import logger

from domain.camera import CameraInfo, CameraMode

__all__ = ["DirectShowCameraCatalog"]

# Форматы, которые OpenCV умеет декодировать через DirectShow; H264/H265 пропускаем
SUPPORTED_FOURCC = ("MJPG", "YUY2", "NV12", "RGB24")
# Сюда мы сами выводим картинку - если читать её же, получится петля
OWN_OUTPUT_CAMERAS = ("OBS Virtual Camera",)


class _Subtypes(dict):
    """pygrabber падает на неизвестных форматах (H264 и т.п.) - достаём FOURCC прямо из GUID"""

    def __missing__(self, guid: str) -> str:
        return bytes.fromhex(guid[1:9])[::-1].decode("ascii", "replace")


class DirectShowCameraCatalog:
    @staticmethod
    def _test_camera(index: int) -> bool:
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        try:
            return bool(cap.read()[0])
        finally:
            cap.release()

    def list_cameras(self) -> list[CameraInfo]:
        """Возвращает список работающих камер с поддерживаемыми режимами"""
        cameras = []
        for camera in self._get_dshow_cameras():
            if camera.name in OWN_OUTPUT_CAMERAS:
                continue
            if self._test_camera(camera.index):
                logger.info(f"{camera} - OK, режимов: {len(camera.modes)}")
                cameras.append(camera)
            else:
                logger.info(f"{camera} - не отдаёт кадры, пропускаю")

        if not cameras:
            logger.error("Нет доступных камер!")
        return cameras

    @classmethod
    def _get_dshow_cameras(cls) -> list[CameraInfo]:
        """Камеры в порядке DirectShow - он совпадает с индексами cv2.CAP_DSHOW"""
        try:
            from pygrabber import dshow_graph

            dshow_graph.subtypes = _Subtypes(dshow_graph.subtypes)
            names = dshow_graph.FilterGraph().get_input_devices()
        except Exception as e:
            logger.error(f"Не удалось получить список камер через DirectShow: {e}")
            return [CameraInfo(index=i, name=f"Camera {i}") for i in range(10)]

        cameras = []
        for index, name in enumerate(names):
            try:
                graph = dshow_graph.FilterGraph()
                graph.add_video_input_device(index)
                formats = graph.get_input_device().get_formats()
            except Exception as e:
                logger.error(f"Не удалось получить режимы камеры [{index}] {name}: {e}")
                formats = []
            cameras.append(CameraInfo(index=index, name=name, modes=cls._pick_modes(formats)))
        return cameras

    @staticmethod
    def _pick_modes(formats: list[dict]) -> list[CameraMode]:
        """Для каждого разрешения оставляет режим с максимальным fps (при равенстве - MJPG)"""
        best: dict[tuple[int, int], CameraMode] = {}
        for f in formats:
            fourcc = f["media_type_str"]
            if fourcc not in SUPPORTED_FOURCC:
                continue
            # В pygrabber min_framerate считается из минимального интервала кадра, т.е. это максимальный fps
            mode = CameraMode(width=f["width"], height=f["height"], fps=round(f["min_framerate"]), fourcc=fourcc)
            current = best.get((mode.width, mode.height))
            if current is None or (mode.fps, mode.fourcc == "MJPG") > (current.fps, current.fourcc == "MJPG"):
                best[(mode.width, mode.height)] = mode
        return sorted(best.values(), key=lambda m: (m.width * m.height, m.fps), reverse=True)


if __name__ == "__main__":
    for cam in DirectShowCameraCatalog().list_cameras():
        print(cam)
        for m in cam.modes:
            print("   ", m)

```

## `infrastructure\camera\face_model.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\infrastructure\camera\face_model.py`

```python
import urllib.request
from pathlib import Path

from loguru import logger

from consts import FACE_LANDMARKER_PATH, FACE_LANDMARKER_URL

__all__ = ["ensure_face_landmarker"]


def ensure_face_landmarker(path: Path = FACE_LANDMARKER_PATH, url: str = FACE_LANDMARKER_URL) -> Path:
    """Возвращает путь к модели, при отсутствии скачивает её"""
    if path.is_file() and path.stat().st_size > 0:
        return path

    logger.info(f"Модель не найдена, скачиваю {url} -> {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".part")
    try:
        with urllib.request.urlopen(url, timeout=30) as response, tmp_path.open("wb") as f:
            while chunk := response.read(64 * 1024):
                f.write(chunk)
        tmp_path.replace(path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    logger.info(f"Модель скачана: {path}")
    return path

```

## `infrastructure\camera\face_tracker.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\infrastructure\camera\face_tracker.py`

```python
from dataclasses import dataclass
from typing import Any

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from domain.pose import Y_SCALE, HeadPose

from .face_model import ensure_face_landmarker

__all__ = ["FaceDetection", "MediaPipeFaceTracker"]


@dataclass(frozen=True, slots=True)
class FaceDetection:
    pose: HeadPose
    landmarks: Any  # Точки лица MediaPipe (нормированные координаты) - для отрисовки сетки


def _head_tilt(landmarks, width: int, height: int) -> float:
    # Внешние уголки глаз; координаты нормированы, поэтому учитываем пропорции кадра
    left_eye, right_eye = landmarks[33], landmarks[263]
    dx = (right_eye.x - left_eye.x) * width
    dy = (right_eye.y - left_eye.y) * height
    return float(np.degrees(np.arctan2(dy, dx)))


class MediaPipeFaceTracker:
    """Находит лицо на кадре и считает позу головы. Не потокобезопасен - используется в потоке камеры"""

    def __init__(self):
        options = vision.FaceLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=str(ensure_face_landmarker())),
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
            num_faces=1,
            # VIDEO-режим отслеживает лицо между кадрами вместо поиска с нуля - быстрее и стабильнее
            running_mode=vision.RunningMode.VIDEO,
        )
        self._detector = vision.FaceLandmarker.create_from_options(options)
        self._last_timestamp_ms = -1

    def detect(self, frame: np.ndarray, timestamp_ms: int) -> FaceDetection | None:
        """frame - BGR-кадр камеры"""
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        # VIDEO-режим требует строго возрастающих меток времени
        timestamp_ms = max(timestamp_ms, self._last_timestamp_ms + 1)
        self._last_timestamp_ms = timestamp_ms
        result = self._detector.detect_for_video(image, timestamp_ms)
        if not result.face_landmarks:
            return None
        landmarks = result.face_landmarks[0]
        height, width = frame.shape[:2]
        pose = HeadPose(tilt=_head_tilt(landmarks, width, height), y=landmarks[0].y * Y_SCALE)
        return FaceDetection(pose=pose, landmarks=landmarks)

    def close(self):
        self._detector.close()

```

## `infrastructure\camera\overlay.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\infrastructure\camera\overlay.py`

```python
"""Отрисовка поверх кадра камеры: сетка лица, линии приседа, подпись"""

import cv2
import numpy as np
from mediapipe.tasks.python.vision import FaceLandmarksConnections

from application.head_tracking import TrackingOverlay
from domain.pose import Y_SCALE

__all__ = ["draw_face_mesh", "draw_sit_lines", "draw_status"]

# Пары индексов точек, образующие рёбра сетки лица
FACE_MESH_EDGES = np.array([(c.start, c.end) for c in FaceLandmarksConnections.FACE_LANDMARKS_TESSELATION])


def draw_face_mesh(frame: np.ndarray, landmarks):
    height, width = frame.shape[:2]
    points = np.array([(lm.x * width, lm.y * height) for lm in landmarks], dtype=np.int32)
    # Все рёбра сетки одним вызовом - на порядок быстрее, чем рисовать их по одному
    cv2.polylines(frame, list(points[FACE_MESH_EDGES]), False, (0, 255, 255), 1, cv2.LINE_AA)


def draw_sit_lines(frame: np.ndarray, overlay: TrackingOverlay):
    """Зелёная линия - откалиброванный верх головы, красная - порог приседа"""
    if not overlay.sit_enabled:
        return
    height, width = frame.shape[:2]
    if overlay.base_y is not None:
        base_px = int(overlay.base_y * height / Y_SCALE)
        cv2.line(frame, (0, base_px), (width, base_px), (0, 255, 0), 1)
    threshold_px = int(overlay.sit_threshold * height / Y_SCALE)
    cv2.line(frame, (0, threshold_px), (width, threshold_px), (0, 0, 255), 2)


def _tilt_text(tilt: float, threshold: float) -> str:
    if tilt > 10:
        return f"Head tilt to the left ({tilt:.2f}) [{threshold}]"
    if tilt < -10:
        return f"Head tilt to the right ({tilt:.2f}) [{threshold}]"
    return f"Head is straight ({tilt:.2f}) [{threshold}]"


def draw_status(frame: np.ndarray, tilt: float, overlay: TrackingOverlay, fps: float):
    cv2.putText(
        frame,
        text=f"{_tilt_text(tilt, overlay.angle_threshold)} {fps:.0f} fps",
        org=(10, 30),
        fontFace=cv2.FONT_HERSHEY_SIMPLEX,
        fontScale=0.7,
        color=(255, 0, 0),
    )

```

## `infrastructure\camera\pipeline.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\infrastructure\camera\pipeline.py`

```python
import threading
import time
from collections.abc import Callable

from loguru import logger

from application.events import Event
from application.head_tracking import HeadTracking
from domain.camera import CameraMode

from .blank_frames import BlankFrameDetector
from .capture import CameraCaptureThread
from .face_tracker import MediaPipeFaceTracker
from .overlay import draw_face_mesh, draw_sit_lines, draw_status
from .preview import PreviewWindow
from .virtual_camera import VirtualCameraOutput

__all__ = ["CameraPipeline"]


class CameraPipeline:
    """
    Цикл обработки в отдельном потоке: кадр камеры -> поза головы -> HeadTracking,
    затем вывод картинки в окно предпросмотра и виртуальную камеру OBS
    """

    def __init__(
        self,
        tracking: HeadTracking,
        # Фабрики компонентов - в тестах подменяются заглушками без камеры и MediaPipe
        capture_factory: Callable[[int, CameraMode | None], CameraCaptureThread] = CameraCaptureThread,
        face_tracker_factory: Callable[[], MediaPipeFaceTracker] = MediaPipeFaceTracker,
        virtual_cam_factory: Callable[..., VirtualCameraOutput] = VirtualCameraOutput,
        preview_factory: Callable[[], PreviewWindow] = PreviewWindow,
    ):
        self._tracking = tracking
        self._capture_factory = capture_factory
        self._face_tracker_factory = face_tracker_factory
        self._virtual_cam_factory = virtual_cam_factory
        self._preview_factory = preview_factory
        self.virtual_cam_failed: Event[str] = Event()

        self._camera_index = 0
        self._camera_mode: CameraMode | None = None  # None - режим камеры по умолчанию
        self._preview_visible = False
        self._overlay = True
        self._virtual_cam = False
        self._virtual_cam_mesh = True

        self._is_on = False
        self._worker: threading.Thread | None = None
        self._blank_frames = BlankFrameDetector()

    @property
    def is_blank(self) -> bool:
        """Камера отдаёт сплошной чёрный кадр - скорее всего, её заняла другая программа"""
        return self._blank_frames.is_blank

    # --- Настройки (из потока UI; поток камеры читает их на каждом кадре) ---

    def set_camera(self, index: int):
        self._camera_index = index

    def set_mode(self, mode: CameraMode | None):
        logger.info(f"Режим камеры: {mode if mode else 'по умолчанию'}")
        self._camera_mode = mode

    def set_preview_visible(self, visible: bool):
        self._preview_visible = visible

    def set_overlay(self, enabled: bool):
        self._overlay = enabled

    def set_virtual_cam(self, enabled: bool):
        logger.info(f"Вывод в виртуальную камеру OBS: {'вкл' if enabled else 'выкл'}")
        self._virtual_cam = enabled

    def set_virtual_cam_mesh(self, enabled: bool):
        self._virtual_cam_mesh = enabled

    # --- Запуск и остановка ---

    def start(self):
        if self._is_on:
            return
        # Предыдущий цикл мог ещё не завершиться
        if self._worker and self._worker.is_alive():
            self._worker.join()
        self._is_on = True
        self._worker = threading.Thread(target=self._safe_run, daemon=True)
        self._worker.start()

    def stop(self, wait: bool = False):
        self._is_on = False
        if wait and self._worker and self._worker is not threading.current_thread():
            self._worker.join(timeout=5)

    def _safe_run(self):
        try:
            self._run()
        except Exception as e:
            logger.exception(f"Ошибка в цикле обработки камеры: {e}")
        finally:
            self._is_on = False

    def _virtual_cam_error(self, message: str):
        # Выключаем вывод, чтобы не пытаться переоткрыть камеру на каждом кадре
        self._virtual_cam = False
        self.virtual_cam_failed.emit(message)

    def _run(self):
        logger.info(f"Запуск камеры {self._camera_index}")
        face_tracker = self._face_tracker_factory()
        active_capture = (self._camera_index, self._camera_mode)
        capture = self._capture_factory(*active_capture)
        capture.start()
        preview = self._preview_factory()
        virtual_cam = self._virtual_cam_factory(on_error=self._virtual_cam_error)

        fps = 0.0
        last_frame_time = time.monotonic()
        last_processed_id = -1
        start_time = time.monotonic()

        try:
            while self._is_on:
                # Камеру или её режим поменяли на ходу - переоткрываем захват
                if (self._camera_index, self._camera_mode) != active_capture:
                    capture.stop()
                    active_capture = (self._camera_index, self._camera_mode)
                    capture = self._capture_factory(*active_capture)
                    capture.start()
                    last_processed_id = -1
                    self._blank_frames.reset()

                # Ждём свежий кадр из потока захвата
                ret, frame, frame_id = capture.wait_for_frame(last_processed_id)
                if not ret or frame is None or frame_id == last_processed_id:
                    continue
                last_processed_id = frame_id
                now = time.monotonic()
                fps = 0.9 * fps + 0.1 / max(now - last_frame_time, 1e-3)  # Сглаженный fps обработки
                last_frame_time = now
                if self._blank_frames.update(frame, now):
                    if self._blank_frames.is_blank:
                        logger.warning(f"Камера {active_capture[0]} отдаёт чёрный кадр - возможно, она занята")
                    else:
                        logger.info("Камера снова отдаёт изображение")

                try:
                    face = face_tracker.detect(frame, int((now - start_time) * 1000))
                    if face:
                        self._tracking.on_pose(face.pose)

                    # Рисование - уже после нажатий клавиш, чтобы не добавлять им задержку
                    show_overlay = self._preview_visible and self._overlay
                    send_virtual_cam = self._virtual_cam
                    mesh_frame = frame
                    if face and (show_overlay or (send_virtual_cam and self._virtual_cam_mesh)):
                        mesh_frame = frame.copy()
                        draw_face_mesh(mesh_frame, face.landmarks)

                    if send_virtual_cam:
                        virtual_cam.send(mesh_frame if self._virtual_cam_mesh else frame, capture.fps)
                    elif virtual_cam.is_open:
                        virtual_cam.close()

                    # send() копирует кадр синхронно, так что дорисовывать предпросмотр поверх уже безопасно
                    if self._preview_visible:
                        if show_overlay:
                            overlay = self._tracking.overlay()
                            draw_sit_lines(mesh_frame, overlay)
                            draw_status(mesh_frame, face.pose.tilt if face else 0.0, overlay, fps)
                        preview.show(mesh_frame)
                    else:
                        preview.hide()
                except Exception as e:
                    logger.error(f"Ошибка обработки кадра: {e}")
        finally:
            self._blank_frames.reset()
            capture.stop()
            virtual_cam.close()
            face_tracker.close()
            preview.close()

```

## `infrastructure\camera\preview.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\infrastructure\camera\preview.py`

```python
import cv2
import numpy as np

__all__ = ["PreviewWindow"]

PREVIEW_TITLE = "Тестирование выбранной камеры"
PREVIEW_WIDTH = 960  # Начальная ширина окна предпросмотра камеры


class PreviewWindow:
    """Окно OpenCV с предпросмотром. Живёт в потоке камеры: окна cv2 привязаны к создавшему их потоку"""

    def __init__(self):
        self._is_shown = False

    def show(self, frame: np.ndarray):
        if not self._is_shown:
            # Окно масштабируемое, иначе кадр 1080p/1440p не влезет в экран
            cv2.namedWindow(PREVIEW_TITLE, cv2.WINDOW_NORMAL)
            height, width = frame.shape[:2]
            preview_width = min(width, PREVIEW_WIDTH)
            cv2.resizeWindow(PREVIEW_TITLE, preview_width, height * preview_width // width)
            self._is_shown = True
        cv2.imshow(PREVIEW_TITLE, frame)
        # waitKey стоит ~2 мс, поэтому крутим цикл событий окна только когда оно показано
        cv2.waitKey(1)

    def hide(self):
        if self._is_shown:
            cv2.destroyWindow(PREVIEW_TITLE)
            self._is_shown = False

    def close(self):
        self.hide()
        cv2.destroyAllWindows()

```

## `infrastructure\camera\virtual_camera.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\infrastructure\camera\virtual_camera.py`

```python
from collections.abc import Callable

import numpy as np
from loguru import logger

__all__ = ["VirtualCameraOutput"]


class VirtualCameraOutput:
    """
    Отдаёт кадры в виртуальную камеру OBS, чтобы физическую камеру держало только это приложение,
    а OBS забирал картинку как "Устройство захвата видео -> OBS Virtual Camera"
    """

    def __init__(self, on_error: Callable[[str], None] | None = None):
        self._on_error = on_error
        self._cam = None
        self._format: tuple[int, int, int] | None = None  # ширина, высота, fps

    @property
    def is_open(self) -> bool:
        return self._cam is not None

    def send(self, frame: np.ndarray, fps: float) -> bool:
        """Отправляет BGR-кадр; при ошибке закрывает камеру, сообщает о ней и возвращает False"""
        height, width = frame.shape[:2]
        fmt = (width, height, max(round(fps), 1))
        try:
            if self._cam is None or self._format != fmt:
                self._open(*fmt)
            self._cam.send(frame)  # type: ignore[union-attr]
            return True
        except Exception as e:
            self.close()
            message = f"Не удалось вывести изображение в виртуальную камеру OBS: {e}"
            logger.error(message)
            if self._on_error:
                self._on_error(message)
            return False

    def _open(self, width: int, height: int, fps: int):
        import pyvirtualcam

        self.close()
        self._cam = pyvirtualcam.Camera(width, height, fps, fmt=pyvirtualcam.PixelFormat.BGR, backend="obs")
        self._format = (width, height, fps)
        logger.info(f"Виртуальная камера: {self._cam.device} {width}x{height} @ {fps} fps")

    def close(self):
        if self._cam is not None:
            self._cam.close()
            logger.info("Виртуальная камера закрыта")
        self._cam = None
        self._format = None

```

## `infrastructure\foreground_window.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\infrastructure\foreground_window.py`

```python
import ctypes
from collections.abc import Sequence
from ctypes import wintypes
from dataclasses import dataclass
from pathlib import PureWindowsPath

from application.ports import ScreenRect
from consts import TARGET_PROCESSES, TARGET_TITLES

__all__ = ["ForegroundWindow", "GameWindowWatcher"]

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


@dataclass(frozen=True, slots=True)
class ForegroundWindow:
    title: str
    process: str  # Имя exe, пустое если процесс не удалось открыть


def _process_name(pid: int) -> str:
    # LIMITED_INFORMATION хватает даже для процессов под защитой античита (BattlEye у PUBG)
    handle = _kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        buffer = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(len(buffer))
        if not _kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
            return ""
        return PureWindowsPath(buffer.value).name
    finally:
        _kernel32.CloseHandle(handle)


class GameWindowWatcher:
    """Следит за активным окном Windows: игра ли это и где её клиентская область"""

    def __init__(
        self,
        target_processes: Sequence[str] = TARGET_PROCESSES,
        target_titles: Sequence[str] = TARGET_TITLES,
    ):
        self._target_processes = {name.lower() for name in target_processes}
        self._target_titles = tuple(target_titles)
        self._process_names: dict[int, str] = {}  # pid -> имя exe, чтобы не открывать процесс каждый раз

    def get_foreground(self) -> ForegroundWindow | None:
        hwnd = _user32.GetForegroundWindow()
        if not hwnd:
            return None
        pid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        title = ctypes.create_unicode_buffer(512)
        _user32.GetWindowTextW(hwnd, title, len(title))
        if pid.value not in self._process_names:
            self._process_names[pid.value] = _process_name(pid.value)
        return ForegroundWindow(title=title.value.strip(), process=self._process_names[pid.value])

    def is_target(self, window: ForegroundWindow | None) -> bool:
        if window is None:
            return False
        if window.process:
            return window.process.lower() in self._target_processes
        # Процесс не открылся - определяем по заголовку
        return any(target in window.title for target in self._target_titles)

    def is_game_active(self) -> bool:
        """Игра на переднем плане; проверка занимает ~20 мкс"""
        return self.is_target(self.get_foreground())

    def foreground_rect(self) -> ScreenRect | None:
        """Клиентская область активного окна в координатах экрана"""
        hwnd = _user32.GetForegroundWindow()
        if not hwnd:
            return None
        rect = wintypes.RECT()
        if not _user32.GetClientRect(hwnd, ctypes.byref(rect)):
            return None
        origin = wintypes.POINT(0, 0)
        if not _user32.ClientToScreen(hwnd, ctypes.byref(origin)):
            return None
        return origin.x, origin.y, rect.right - rect.left, rect.bottom - rect.top

```

## `infrastructure\keyboard.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\infrastructure\keyboard.py`

```python
import time

import pydirectinput

__all__ = ["DirectInputKeySender"]

# Отключаем искусственные задержки pydirectinput, чтобы не тормозить цикл обработки камеры
pydirectinput.PAUSE = 0.0
pydirectinput.FAILSAFE = False  # type: ignore

# Играм на DirectX нужна микро-задержка, чтобы заметить "клик" (иначе он слишком быстрый)
TAP_SECONDS = 0.015


class DirectInputKeySender:
    """Нажатия через DirectInput-скан-коды: их видят игры, игнорирующие виртуальные клавиши"""

    def key_down(self, button: str):
        pydirectinput.keyDown(button.lower())

    def key_up(self, button: str):
        pydirectinput.keyUp(button.lower())

    def tap(self, button: str):
        pydirectinput.keyDown(button.lower())
        time.sleep(TAP_SECONDS)
        pydirectinput.keyUp(button.lower())

```

## `infrastructure\settings_json.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\infrastructure\settings_json.py`

```python
import json
import os
from dataclasses import asdict, fields
from pathlib import Path
from typing import Any

from loguru import logger

from domain.bindings import Action, GameBindings, KeyBinding, KeyMode
from domain.camera import CameraMode
from domain.settings import AppSettings

__all__ = ["SETTINGS_PATH", "JsonSettingsRepository"]

# Рядом с exe писать нельзя, если программа лежит в Program Files, поэтому храним в профиле пользователя
SETTINGS_PATH = Path(os.environ.get("APPDATA", Path.home())) / "VRMonitor" / "settings.json"

# До версии с bindings привязки хранились в "game", а режим - русской подписью из интерфейса
_LEGACY_MODES = {"Удержание": KeyMode.HOLD, "Нажатие": KeyMode.PRESS}


def _parse_binding(data: dict[str, Any]) -> KeyBinding:
    mode = KeyMode(data["mode"]) if "mode" in data else _LEGACY_MODES[data["hold_or_press"]]
    return KeyBinding(button=data["button"], mode=mode)


def _parse_bindings(data: dict[str, Any]) -> GameBindings:
    bindings = GameBindings.default()
    for action in Action:
        if raw := data.get(action.value):
            bindings = bindings.with_binding(action, _parse_binding(raw))
    return bindings


class JsonSettingsRepository:
    def __init__(self, path: Path = SETTINGS_PATH):
        self._path = path

    def load(self) -> AppSettings:
        """Загружает настройки; при отсутствии или порче файла возвращает значения по умолчанию"""
        if not self._path.is_file():
            return AppSettings()
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            plain = {f.name for f in fields(AppSettings)} - {"bindings", "camera_mode"}
            settings = AppSettings(**{k: v for k, v in data.items() if k in plain})
            if mode := data.get("camera_mode"):
                settings.camera_mode = CameraMode(**mode)
            if bindings := data.get("bindings") or data.get("game"):
                settings.bindings = _parse_bindings(bindings)
            return settings
        except Exception as e:
            logger.error(f"Не удалось прочитать настройки {self._path}, использую значения по умолчанию: {e}")
            return AppSettings()

    def save(self, settings: AppSettings):
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as e:
            logger.error(f"Не удалось сохранить настройки {self._path}: {e}")

```

## `infrastructure\stance_detector.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\infrastructure\stance_detector.py`

```python
from dataclasses import dataclass

import cv2
import numpy as np

from domain.pose import Stance

__all__ = [
    "Region",
    "ScreenStanceDetector",
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

    # Цветной фон (небо, трава, песок) отсекается насыщенностью; спутать иконку можно только с бесцветным.
    # Если бесцветного - больше половины области (снег, бетон), порог яркости поднимаем над ним.
    # Иконка занимает малую часть области, так что медиана - это яркость фона
    colorless = saturation <= _MAX_ICON_SATURATION
    background = int(np.median(value[colorless])) if np.count_nonzero(colorless) > colorless.size // 2 else 0
    threshold = max(_MIN_ICON_VALUE, background + _ICON_CONTRAST)
    if threshold > 245:
        return None  # Фон почти белый - иконку от него не отличить
    mask = ((value >= threshold) & colorless).astype(np.uint8)

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


class ScreenStanceDetector:
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

```

## `main.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\main.py`

```python
import sys

from PySide6.QtWidgets import QApplication

from application.app import App
from application.game_keys import GameKeys
from application.head_tracking import HeadTracking
from application.input_controller import InputController
from infrastructure.camera.catalog import DirectShowCameraCatalog
from infrastructure.camera.pipeline import CameraPipeline
from infrastructure.foreground_window import GameWindowWatcher
from infrastructure.keyboard import DirectInputKeySender
from infrastructure.settings_json import JsonSettingsRepository
from infrastructure.stance_detector import ScreenStanceDetector
from ui import MainWindow


def build_app() -> App:
    """Точка сборки: единственное место, где конкретные реализации связываются друг с другом"""
    input_controller = InputController(
        keys=GameKeys(DirectInputKeySender()),
        window=GameWindowWatcher(),
        stance_probe=ScreenStanceDetector(),
    )
    tracking = HeadTracking(input_controller)
    return App(
        settings_repository=JsonSettingsRepository(),
        camera_catalog=DirectShowCameraCatalog(),
        camera=CameraPipeline(tracking),
        tracking=tracking,
        input_controller=input_controller,
    )


def main():
    try:
        qt_app = QApplication(sys.argv)
        main_window = MainWindow(build_app())
        main_window.show()
        sys.exit(qt_app.exec())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()

```

## `ui\__init__.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\ui\__init__.py`

```python
from .main_window import MainWindow

```

## `ui\bridge.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\ui\bridge.py`

```python
from PySide6.QtCore import QObject, QTimer, Signal

from application.app import App
from consts import POLL_INTERVAL_MS

__all__ = ["QtBridge"]

SAVE_DELAY_MS = 500


class QtBridge(QObject):
    """
    Связь App с Qt: события приложения (в т.ч. из потока камеры) приходят сюда в поток GUI
    через очередь событий Qt; таймеры опрашивают окно игры и сохраняют настройки
    """

    game_active_changed = Signal(bool)
    stance_changed = Signal(object)  # Stance | None
    calibrated = Signal(int)
    virtual_cam_failed = Signal(str)

    def __init__(self, app: App, parent: QObject | None = None):
        super().__init__(parent)
        self._app = app

        app.game_active_changed.connect(self.game_active_changed.emit)
        app.stance_changed.connect(self.stance_changed.emit)
        app.calibrated.connect(self.calibrated.emit)
        app.virtual_cam_failed.connect(self.virtual_cam_failed.emit)

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(app.poll)
        self._poll_timer.start(POLL_INTERVAL_MS)

        # Настройки сохраняются с небольшой задержкой, чтобы не писать файл на каждый шаг слайдера
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(SAVE_DELAY_MS)
        self._save_timer.timeout.connect(app.save)
        app.settings_changed.connect(lambda _: self._save_timer.start())

    def shutdown(self):
        self._poll_timer.stop()
        self._save_timer.stop()
        self._app.shutdown()

```

## `ui\camera_list.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\ui\camera_list.py`

```python
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from domain.camera import CameraInfo, CameraMode
from ui.pointed_combo_box import PointedComboBox

__all__ = ["CameraSelectWidget"]

DEFAULT_MODE_TITLE = "Режим по умолчанию"


class CameraSelectWidget(QWidget):
    camera_changed = Signal(int)
    mode_changed = Signal(object)  # CameraMode | None

    def __init__(self, parent: QWidget, cameras: list[CameraInfo]):
        super().__init__(parent)

        self._layout: QVBoxLayout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        self.camera_box = PointedComboBox(self)
        self.camera_box.currentIndexChanged.connect(self._on_camera_select)
        self._layout.addWidget(self.camera_box)

        self.mode_box = PointedComboBox(self)
        self.mode_box.setToolTip("Разрешение и частота кадров камеры")
        self.mode_box.currentIndexChanged.connect(self._on_mode_select)
        self._layout.addWidget(self.mode_box)

        self.camera_box.add_items(cameras)

    @staticmethod
    def _find_row(box: PointedComboBox, predicate) -> int | None:
        for row in range(box.count()):
            data = box.itemData(row, Qt.ItemDataRole.UserRole + 1)
            if data and predicate(data):
                return row
        return None

    def select_camera(self, index: int):
        """Выбирает камеру по её системному индексу, если она доступна"""
        row = self._find_row(self.camera_box, lambda camera: camera.index == index)
        if row is not None:
            self.camera_box.setCurrentIndex(row)

    def select_mode(self, mode: CameraMode | None):
        """Выбирает режим текущей камеры; если камера его не поддерживает - режим по умолчанию"""
        row = self._find_row(self.mode_box, lambda m: m == mode) if mode else None
        self.mode_box.setCurrentIndex(row if row is not None else 0)

    def _update_mode_list(self, camera: CameraInfo | None):
        self.mode_box.blockSignals(True)
        self.mode_box.clear()
        self.mode_box.add_items(camera.modes if camera else [], add_empty=(True, DEFAULT_MODE_TITLE))
        self.mode_box.blockSignals(False)
        self._on_mode_select()

    def _on_camera_select(self):
        camera: CameraInfo | None = self.camera_box.current_data
        self._update_mode_list(camera)
        if camera:
            self.camera_changed.emit(camera.index)

    def _on_mode_select(self):
        self.mode_changed.emit(self.mode_box.current_data)

    @property
    def current_camera_index(self) -> int | None:
        camera: CameraInfo | None = self.camera_box.current_data
        return camera.index if camera else None

    @property
    def current_mode(self) -> CameraMode | None:
        return self.mode_box.current_data

```

## `ui\labels.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\ui\labels.py`

```python
"""Подписи для доменных значений. Только для отображения - в настройках хранятся сами значения"""

from domain.bindings import Action, KeyMode
from domain.pose import Stance

__all__ = ["ACTION_TITLES", "KEY_MODE_HINTS", "KEY_MODE_TITLES", "STANCE_TITLES"]

ACTION_TITLES = {
    Action.LEAN_LEFT: "Влево",
    Action.LEAN_RIGHT: "Вправо",
    Action.SIT: "Клавиша",
}

KEY_MODE_TITLES = {
    KeyMode.HOLD: "Удерживать",
    KeyMode.PRESS: "Нажимать",
}

KEY_MODE_HINTS = {
    KeyMode.HOLD: "Клавиша зажата, пока действие активно (как в игре с режимом «удержание»)",
    KeyMode.PRESS: "Одно нажатие включает действие, повторное - выключает (режим «переключение»)",
}

STANCE_TITLES = {
    Stance.STAND: "стоит",
    Stance.CROUCH: "сидит",
    Stance.PRONE: "лежит",
}

```

## `ui\main_window.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\ui\main_window.py`

```python
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from application.app import App
from consts import TARGET_GAME_NAME
from domain.bindings import Action, GameBindings, KeyBinding
from domain.pose import Y_SCALE
from ui.bridge import QtBridge
from ui.camera_list import CameraSelectWidget
from ui.labels import ACTION_TITLES, STANCE_TITLES
from ui.widgets.binding_row import BindingRow
from ui.widgets.threshold_gauge import ThresholdGauge

__all__ = ["MainWindow"]

LIVE_REFRESH_MS = 100  # Как часто обновлять живые подсказки

BLANK_FRAME_WARNING = (
    "Камера отдаёт чёрный кадр. Скорее всего, её заняла другая программа — например, OBS, "
    "где эта камера добавлена источником. Уберите её из OBS и добавьте вместо неё "
    "«Устройство захвата видео» → «OBS Virtual Camera» (галочка «Вывод в OBS»). "
    "Также проверьте, не закрыт ли объектив шторкой."
)
MIN_ANGLE, MAX_ANGLE = 1, 60
LABEL_COLUMN_WIDTH = 64  # Шкалы в разных секциях начинаются с одной вертикали

STYLE = """
QPushButton#primary { font-size: 15px; font-weight: 600; padding: 10px 18px; }
QPushButton#primary:checked { background: #2f9e44; color: white; border: 1px solid #2b8a3e; }
QLabel[chip] { border-radius: 10px; padding: 3px 10px; }
QLabel[chip="ok"] { background: rgba(47, 158, 68, 0.22); color: palette(text); }
QLabel[chip="warn"] { background: rgba(232, 89, 12, 0.25); color: palette(text); }
QLabel[chip="off"] { background: rgba(128, 128, 128, 0.18); color: palette(placeholder-text); }
QLabel[hint] { color: palette(placeholder-text); }
QLabel[value] { font-weight: 600; min-width: 42px; }
"""


def _hint(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setProperty("hint", True)
    label.setWordWrap(True)
    return label


def _set_chip(label: QLabel, text: str, state: str):
    label.setText(text)
    if label.property("chip") != state:
        label.setProperty("chip", state)
        label.style().unpolish(label)
        label.style().polish(label)


class MainWindow(QMainWindow):
    def __init__(self, app: App):
        super().__init__()
        self._app = app
        # Сигналы из потока камеры подключаем только к методам виджетов: тогда Qt вызывает их в потоке GUI
        self._bridge = QtBridge(app, self)

        self.setWindowTitle("VR-монитор kek8")
        self.setStyleSheet(STYLE)
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)

        layout.addLayout(self._build_header())
        layout.addWidget(self._build_camera_group())
        layout.addWidget(self._build_lean_group())
        layout.addWidget(self._build_sit_group())
        layout.addWidget(self._build_game_group())
        layout.addStretch()

        self._bridge.game_active_changed.connect(self._refresh_status)
        self._bridge.stance_changed.connect(self._refresh_status)
        self._bridge.calibrated.connect(self._on_calibrated)
        self._bridge.virtual_cam_failed.connect(self._on_virtual_cam_failed)

        self._live_timer = QTimer(self)
        self._live_timer.timeout.connect(self._refresh_live)
        self._live_timer.start(LIVE_REFRESH_MS)
        self._refresh_live()

        self.setMinimumWidth(480)
        self.adjustSize()

    # --- Построение ---

    def _build_header(self) -> QVBoxLayout:
        self.run_button = QPushButton("Включить распознавание", self)
        self.run_button.setObjectName("primary")
        self.run_button.setCheckable(True)
        self.run_button.toggled.connect(self._on_run_toggled)

        self.face_chip = QLabel(self)
        self.game_chip = QLabel(self)
        chips = QHBoxLayout()
        chips.addWidget(self.face_chip)
        chips.addWidget(self.game_chip)
        chips.addStretch()

        self.blank_warning = QLabel(BLANK_FRAME_WARNING, self)
        self.blank_warning.setProperty("chip", "warn")
        self.blank_warning.setWordWrap(True)
        self.blank_warning.setVisible(False)

        header = QVBoxLayout()
        header.addWidget(self.run_button)
        header.addLayout(chips)
        header.addWidget(self.blank_warning)
        return header

    def _build_camera_group(self) -> QGroupBox:
        settings = self._app.settings
        group = QGroupBox("Камера", self)
        grid = QGridLayout(group)

        # Сохранённая камера могла пропасть, поэтому после выбора применяем то, что реально выбрано
        self.camera_select = CameraSelectWidget(group, self._app.list_cameras())
        if settings.camera_index is not None:
            self.camera_select.select_camera(settings.camera_index)
        self.camera_select.select_mode(settings.camera_mode)
        if self.camera_select.current_camera_index is not None:
            self._app.update(
                camera_index=self.camera_select.current_camera_index,
                camera_mode=self.camera_select.current_mode,
            )
        self.camera_select.camera_changed.connect(lambda index: self._app.update(camera_index=index))
        self.camera_select.mode_changed.connect(lambda mode: self._app.update(camera_mode=mode))

        self.preview_button = QPushButton("Показать камеру", group)
        self.preview_button.setCheckable(True)
        self.preview_button.setToolTip("Окно с изображением камеры; работает, пока распознавание включено")
        self.preview_button.toggled.connect(self._on_preview_toggled)
        self.visualize_box = self._setting_checkbox(
            group, "Разметка в окне камеры", "visualize", "Сетка лица, линии приседа и угол наклона поверх изображения"c
        )
        self.virtual_cam_box = self._setting_checkbox(
            group,
            "Вывод в OBS",
            "virtual_cam",
            "Отдавать изображение камеры в OBS Virtual Camera (работает, пока распознавание включено).\n"
            "В OBS добавьте источник «Устройство захвата видео» → «OBS Virtual Camera».\n"
            "Кнопка «Запустить виртуальную камеру» в самом OBS при этом должна быть выключена.",
        )
        self.virtual_cam_mesh_box = self._setting_checkbox(
            group, "Сетка лица в OBS", "virtual_cam_mesh", "Рисовать сетку лица на изображении для OBS"
        )
        self.virtual_cam_mesh_box.setEnabled(settings.virtual_cam)
        self.virtual_cam_box.toggled.connect(self.virtual_cam_mesh_box.setEnabled)

        grid.addWidget(self.camera_select, 0, 0, 1, 2)
        grid.addWidget(self.preview_button, 1, 0)
        grid.addWidget(self.visualize_box, 1, 1)
        grid.addWidget(self.virtual_cam_box, 2, 0)
        grid.addWidget(self.virtual_cam_mesh_box, 2, 1)
        return group

    def _build_lean_group(self) -> QGroupBox:
        settings = self._app.settings
        group = QGroupBox("Наклоны", self)
        grid = QGridLayout(group)

        self.angle_gauge = ThresholdGauge(MIN_ANGLE, MAX_ANGLE, settings.angle_threshold, group)
        self.angle_gauge.setToolTip("Наклон головы, после которого персонаж наклоняется")
        self.angle_value = QLabel(group)
        self.angle_value.setProperty("value", True)
        self.angle_live = _hint()
        self.angle_gauge.value_changed.connect(self._on_angle_changed)
        self._show_angle(self.angle_gauge.value)

        self.left_row = self._binding_row(group, Action.LEAN_LEFT)
        self.right_row = self._binding_row(group, Action.LEAN_RIGHT)

        grid.setColumnMinimumWidth(0, LABEL_COLUMN_WIDTH)
        grid.addWidget(QLabel("Порог", group), 0, 0)
        grid.addWidget(self.angle_gauge, 0, 1)
        grid.addWidget(self.angle_value, 0, 2)
        grid.addWidget(self.angle_live, 1, 1, 1, 2)
        grid.addWidget(QLabel(ACTION_TITLES[Action.LEAN_LEFT], group), 2, 0)
        grid.addWidget(self.left_row, 2, 1, 1, 2)
        grid.addWidget(QLabel(ACTION_TITLES[Action.LEAN_RIGHT], group), 3, 0)
        grid.addWidget(self.right_row, 3, 1, 1, 2)
        grid.setColumnStretch(1, 1)
        return group

    def _build_sit_group(self) -> QGroupBox:
        settings = self._app.settings
        group = QGroupBox("Приседания", self)
        group.setCheckable(True)
        group.setChecked(settings.sit_enabled)
        group.toggled.connect(lambda enabled: self._app.update(sit_enabled=enabled))
        grid = QGridLayout(group)

        self.sit_gauge = ThresholdGauge(1, Y_SCALE, settings.sit_y, group)
        self.sit_gauge.setToolTip(
            "Линия на высоте кадра (слева - верх, справа - низ).\nГолова опустилась правее линии - персонаж садится"
        )
        self.sit_value = QLabel(group)
        self.sit_value.setProperty("value", True)
        self.sit_live = _hint()
        self.sit_gauge.value_changed.connect(self._on_sit_threshold_changed)
        self._show_sit_threshold(settings.sit_y)

        self.auto_calibrate_box = self._setting_checkbox(
            group,
            "Авто-калибровка",
            "auto_calibrate",
            "Если голова неподвижна 20 секунд стоя, её положение считается верхним,\n"
            "и линия приседа сдвигается вместе с ним (зелёная отметка на шкале)",
        )
        self.sit_row = self._binding_row(group, Action.SIT)

        grid.setColumnMinimumWidth(0, LABEL_COLUMN_WIDTH)
        grid.addWidget(QLabel("Линия", group), 0, 0)
        grid.addWidget(self.sit_gauge, 0, 1)
        grid.addWidget(self.sit_value, 0, 2)
        grid.addWidget(self.sit_live, 1, 1, 1, 2)
        grid.addWidget(self.auto_calibrate_box, 2, 1, 1, 2)
        grid.addWidget(QLabel(ACTION_TITLES[Action.SIT], group), 3, 0)
        grid.addWidget(self.sit_row, 3, 1, 1, 2)
        grid.setColumnStretch(1, 1)
        return group

    def _build_game_group(self) -> QGroupBox:
        group = QGroupBox(TARGET_GAME_NAME, self)
        layout = QVBoxLayout(group)
        layout.addWidget(
            self._setting_checkbox(
                group,
                f"Нажимать клавиши только в {TARGET_GAME_NAME}",
                "only_in_game",
                f"Клавиши уходят, только когда {TARGET_GAME_NAME} на переднем плане.\n"
                "При переключении на другое окно зажатые клавиши отпускаются.",
            )
        )
        layout.addWidget(
            self._setting_checkbox(
                group,
                "Учитывать позу персонажа",
                "detect_stance",
                "Поза определяется по иконке слева от полосы здоровья.\n"
                "Пока персонаж лежит, приседания с камеры не нажимаются,\n"
                "а присед, сделанный вручную, принимается из игры.",
            )
        )
        reset = QPushButton("Клавиши по умолчанию", group)
        reset.setFlat(True)
        reset.clicked.connect(self._reset_bindings)
        layout.addWidget(reset, alignment=Qt.AlignmentFlag.AlignLeft)
        return group

    def _setting_checkbox(self, parent: QWidget, text: str, setting: str, tooltip: str | None = None) -> QCheckBox:
        """Галочка, напрямую связанная с булевой настройкой"""
        checkbox = QCheckBox(text, parent)
        if tooltip:
            checkbox.setToolTip(tooltip)
        checkbox.setChecked(getattr(self._app.settings, setting))
        checkbox.toggled.connect(lambda value: self._app.update(**{setting: value}))
        return checkbox

    def _binding_row(self, parent: QWidget, action: Action) -> BindingRow:
        row = BindingRow(self._app.settings.bindings.get(action), parent)
        row.binding_changed.connect(lambda binding: self._on_binding_changed(action, binding))
        return row

    # --- Реакция на действия пользователя ---

    def _on_run_toggled(self, running: bool):
        self.run_button.setText("Выключить распознавание" if running else "Включить распознавание")
        self._app.set_running(running)
        self._refresh_live()

    def _on_preview_toggled(self, visible: bool):
        self.preview_button.setText("Скрыть камеру" if visible else "Показать камеру")
        self._app.set_preview_visible(visible)

    def _on_angle_changed(self, angle: int):
        self._show_angle(angle)
        self._app.update(angle_threshold=angle)

    def _on_sit_threshold_changed(self, threshold: int):
        self._show_sit_threshold(threshold)
        self._app.update(sit_y=threshold)

    def _on_binding_changed(self, action: Action, binding: KeyBinding):
        self._app.update(bindings=self._app.settings.bindings.with_binding(action, binding))

    def _reset_bindings(self):
        bindings = GameBindings.default()
        self._app.update(bindings=bindings)
        for row, action in ((self.left_row, Action.LEAN_LEFT), (self.right_row, Action.LEAN_RIGHT)):
            row.set_binding(bindings.get(action))
        self.sit_row.set_binding(bindings.sit)

    # --- Реакция на события приложения ---

    def _on_calibrated(self, threshold: int):
        self.sit_gauge.set_value(threshold, emit=False)
        self._show_sit_threshold(threshold)
        self._app.update(sit_y=threshold)

    def _on_virtual_cam_failed(self, message: str):
        self.virtual_cam_box.setChecked(False)
        QMessageBox.warning(
            self,
            "Вывод в OBS",
            f"{message}\n\nПроверьте, что OBS Studio установлен, "
            "а его собственная виртуальная камера («Запустить виртуальную камеру») выключена.",
        )

    # --- Отображение ---

    def _show_angle(self, angle: int):
        self.angle_value.setText(f"{angle}°")

    def _show_sit_threshold(self, threshold: int):
        self.sit_value.setText(f"{threshold * 100 // Y_SCALE}%" if threshold else "—")

    def _refresh_live(self):
        live = self._app.live_head() if self._app.is_running else None
        pose = live.pose if live else None

        if pose is None:
            self.angle_gauge.set_live(None)
            self.sit_gauge.set_live(None)
            idle = "Лицо не найдено" if self._app.is_running else "Положение головы появится после включения"
            self.angle_live.setText(idle)
            self.sit_live.setText(idle)
        else:
            tilt = abs(pose.tilt)
            side = "влево" if pose.tilt > 0 else "вправо"
            self.angle_gauge.set_live(tilt)
            self.angle_live.setText(
                f"Сейчас {tilt:.0f}° {side}" + (" — наклон" if self.angle_gauge.is_live_active else "")
            )
            self.sit_gauge.set_live(pose.y)
            if not self._app.settings.sit_y:
                self.sit_live.setText("Линия не задана: встаньте ровно и перетащите её чуть ниже головы")
            else:
                self.sit_live.setText(
                    f"Голова на {pose.y * 100 / Y_SCALE:.0f}% высоты кадра"
                    + (" — присед" if self.sit_gauge.is_live_active else "")
                )
        self.sit_gauge.set_reference(live.base_y if live else None)
        self._refresh_status()

    def _refresh_status(self, *_):
        is_blank = self._app.is_camera_blank
        if self.blank_warning.isHidden() == is_blank:
            self.blank_warning.setVisible(is_blank)
            self.adjustSize()

        if not self._app.is_running:
            _set_chip(self.face_chip, "Камера выключена", "off")
        elif is_blank:
            _set_chip(self.face_chip, "Чёрный кадр с камеры", "warn")
        elif self._app.live_head().pose is None:
            _set_chip(self.face_chip, "Лицо не найдено", "warn")
        else:
            _set_chip(self.face_chip, "Лицо найдено", "ok")

        if self._app.is_game_active:
            stance = STANCE_TITLES.get(self._app.stance)
            _set_chip(self.game_chip, f"{TARGET_GAME_NAME} в фокусе" + (f", {stance}" if stance else ""), "ok")
        elif self._app.settings.only_in_game:
            _set_chip(self.game_chip, f"{TARGET_GAME_NAME} не в фокусе — клавиши не нажимаются", "off")
        else:
            _set_chip(self.game_chip, f"{TARGET_GAME_NAME} не в фокусе", "off")

    def closeEvent(self, event):
        self._live_timer.stop()
        self._bridge.shutdown()

```

## `ui\pointed_combo_box.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\ui\pointed_combo_box.py`

```python
from typing import Any

from PySide6.QtCore import QObject
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QComboBox, QWidget

__all__ = ["PointedComboBox"]

TOOLTIP_LINE_LENGTH = 50


class PointedComboBox(QComboBox):
    """Выпадающий список, где у каждого пункта есть объект данных (подпись - его repr)"""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setMaxVisibleItems(10)
        self._model = QStandardItemModel()
        self.setModel(self._model)
        self.currentIndexChanged.connect(self._update_tooltip)

    def _update_tooltip(self):
        # Длинные названия камер переносим по словам
        lines, line = [], ""
        for word in self.currentText().split(" "):
            if line and len(line) + len(word) > TOOLTIP_LINE_LENGTH:
                lines.append(line.strip())
                line = ""
            line += word + " "
        lines.append(line.strip())
        self.setToolTip("\n".join(lines))

    def add_items(self, items: list, add_empty: tuple[bool, str] = (False, "")):
        if add_empty[0]:
            item = QStandardItem(add_empty[1])
            item.setData(None)
            self._model.appendRow(item)
        for data in items:
            item = QStandardItem(repr(data))
            item.setData(data)
            self._model.appendRow(item)
        if self._model.rowCount():
            self.setCurrentIndex(0)

    @property
    def current_data(self) -> Any:
        item = self._model.item(self.currentIndex())
        if item:
            return item.data()
        return None

    def wheelEvent(self, event):
        # Прокрутка колесом не должна случайно переключать камеру - отдаём её родителю
        parent: QObject | None = self.parent()
        if isinstance(parent, QWidget):
            parent.wheelEvent(event)

```

## `ui\widgets\__init__.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\ui\widgets\__init__.py`

```python

```

## `ui\widgets\binding_row.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\ui\widgets\binding_row.py`

```python
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QWidget

from domain.bindings import KeyBinding, KeyMode
from ui.labels import KEY_MODE_HINTS, KEY_MODE_TITLES
from ui.widgets.key_capture import KeyCaptureButton

__all__ = ["BindingRow"]


class BindingRow(QWidget):
    """Клавиша и режим её нажатия для одного действия"""

    binding_changed = Signal(object)  # KeyBinding

    def __init__(self, binding: KeyBinding, parent: QWidget | None = None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.key_button = KeyCaptureButton(binding.button, self)
        self.key_button.key_changed.connect(self._emit)
        self.mode_box = QComboBox(self)
        for mode in KeyMode:
            self.mode_box.addItem(KEY_MODE_TITLES[mode], mode)
            self.mode_box.setItemData(self.mode_box.count() - 1, KEY_MODE_HINTS[mode], Qt.ItemDataRole.ToolTipRole)
        self.mode_box.setCurrentIndex(self.mode_box.findData(binding.mode))
        self.mode_box.currentIndexChanged.connect(self._emit)

        layout.addWidget(self.key_button)
        layout.addWidget(self.mode_box, 1)

    def set_binding(self, binding: KeyBinding):
        self.key_button.set_button(binding.button)
        self.mode_box.blockSignals(True)
        self.mode_box.setCurrentIndex(self.mode_box.findData(binding.mode))
        self.mode_box.blockSignals(False)

    def _emit(self, *_):
        self.binding_changed.emit(KeyBinding(button=self.key_button.button, mode=self.mode_box.currentData()))

```

## `ui\widgets\key_capture.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\ui\widgets\key_capture.py`

```python
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QPushButton, QWidget

__all__ = ["KeyCaptureButton", "key_title"]

# Клавиши Qt -> имена pydirectinput (буквы и цифры передаются как есть)
_SPECIAL_KEYS = {
    Qt.Key.Key_Space: "space",
    Qt.Key.Key_Control: "ctrl",
    Qt.Key.Key_Shift: "shift",
    Qt.Key.Key_Alt: "alt",
    Qt.Key.Key_Tab: "tab",
    Qt.Key.Key_CapsLock: "capslock",
    Qt.Key.Key_Left: "left",
    Qt.Key.Key_Right: "right",
    Qt.Key.Key_Up: "up",
    Qt.Key.Key_Down: "down",
    **{getattr(Qt.Key, f"Key_F{n}"): f"f{n}" for n in range(1, 13)},
}

_TITLES = {"space": "Пробел", "ctrl": "Ctrl", "shift": "Shift", "alt": "Alt", "tab": "Tab", "capslock": "Caps Lock"}

_WAITING_TEXT = "Жду клавишу…"


def key_title(button: str) -> str:
    """Подпись клавиши для интерфейса"""
    return _TITLES.get(button.lower(), button.upper())


def _key_name(event: QKeyEvent) -> str | None:
    if name := _SPECIAL_KEYS.get(Qt.Key(event.key())):
        return name
    # По коду клавиши, а не по тексту: так работает и в русской раскладке
    key = event.key()
    if Qt.Key.Key_A <= key <= Qt.Key.Key_Z or Qt.Key.Key_0 <= key <= Qt.Key.Key_9:
        return chr(key).lower()
    return None


class KeyCaptureButton(QPushButton):
    """Кнопка с назначенной клавишей: нажмите на неё, затем нужную клавишу. Esc - отмена"""

    key_changed = Signal(str)

    def __init__(self, button: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._button = button
        self.setCheckable(True)
        self.setFixedWidth(120)  # Не меняется при «Жду клавишу…», соседние поля не прыгают
        self.setToolTip("Нажмите, затем нажмите клавишу на клавиатуре. Esc - отмена")
        self.toggled.connect(self._on_toggled)
        self._refresh()

    @property
    def button(self) -> str:
        return self._button

    def set_button(self, button: str):
        self._button = button
        self._refresh()

    def _refresh(self):
        self.setText(_WAITING_TEXT if self.isChecked() else key_title(self._button))

    def _on_toggled(self, checked: bool):
        self._refresh()
        if checked:
            self.setFocus()
            self.grabKeyboard()
        else:
            self.releaseKeyboard()

    def keyPressEvent(self, event: QKeyEvent):
        if not self.isChecked():
            super().keyPressEvent(event)
            return
        if event.key() == Qt.Key.Key_Escape:
            self.setChecked(False)
            return
        if (name := _key_name(event)) is None:
            return  # Неподдерживаемая клавиша - ждём другую
        self._button = name
        self.setChecked(False)
        self.key_changed.emit(name)

    def focusOutEvent(self, event):
        self.setChecked(False)
        super().focusOutEvent(event)

```

## `ui\widgets\threshold_gauge.py`

**Path:** `D:\pet-projects\python\VRMonitor\src\ui\widgets\threshold_gauge.py`

```python
from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

__all__ = ["ThresholdGauge"]

# Цвет срабатывания: читается и на светлой, и на тёмной теме
ACTIVE_COLOR = QColor("#e8590c")
REFERENCE_COLOR = QColor("#2f9e44")

_HANDLE_RADIUS = 8
_TRACK_HEIGHT = 6
_MARKER_HALF_WIDTH = 5


class ThresholdGauge(QWidget):
    """
    Шкала порога: значение перетаскивается мышью или стрелками, правее порога - зона срабатывания.
    Живой маркер показывает текущее измерение и подсвечивается, когда оно в зоне срабатывания
    """

    value_changed = Signal(int)

    def __init__(self, minimum: int, maximum: int, value: int, parent: QWidget | None = None):
        super().__init__(parent)
        self._minimum = minimum
        self._maximum = maximum
        self._value = self._clamp(value)
        self._live: float | None = None
        self._reference: float | None = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def sizeHint(self) -> QSize:
        return QSize(220, 2 * _HANDLE_RADIUS + 14)

    def minimumSizeHint(self) -> QSize:
        return QSize(120, self.sizeHint().height())

    # --- Значения ---

    @property
    def value(self) -> int:
        return self._value

    def set_value(self, value: int, emit: bool = True):
        value = self._clamp(value)
        if value == self._value:
            return
        self._value = value
        self.update()
        if emit:
            self.value_changed.emit(value)

    def set_live(self, value: float | None):
        """Текущее измерение; None - измерения нет"""
        if value != self._live:
            self._live = value
            self.update()

    def set_reference(self, value: float | None):
        """Дополнительная отметка (например, откалиброванный верх головы)"""
        if value != self._reference:
            self._reference = value
            self.update()

    @property
    def is_live_active(self) -> bool:
        return self._live is not None and self._live > self._value

    def _clamp(self, value: float) -> int:
        return int(min(max(round(value), self._minimum), self._maximum))

    # --- Геометрия ---

    def _track_rect(self) -> QRectF:
        left = _HANDLE_RADIUS + 1
        width = self.width() - 2 * left
        return QRectF(left, (self.height() - _TRACK_HEIGHT) / 2, width, _TRACK_HEIGHT)

    def _x_for(self, value: float) -> float:
        track = self._track_rect()
        span = self._maximum - self._minimum or 1
        ratio = (min(max(value, self._minimum), self._maximum) - self._minimum) / span
        return track.left() + ratio * track.width()

    def _value_at(self, x: float) -> int:
        track = self._track_rect()
        ratio = (x - track.left()) / (track.width() or 1)
        return self._clamp(self._minimum + ratio * (self._maximum - self._minimum))

    # --- Отрисовка ---

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self.palette()
        enabled = self.isEnabled()
        track = self._track_rect()
        center_y = track.center().y()
        handle_x = self._x_for(self._value)

        # Дорожка и зона срабатывания правее порога
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(palette.color(QPalette.ColorRole.Mid))
        painter.drawRoundedRect(track, _TRACK_HEIGHT / 2, _TRACK_HEIGHT / 2)
        zone = QRectF(QPointF(handle_x, track.top()), track.bottomRight())
        zone_color = QColor(ACTIVE_COLOR if enabled else palette.color(QPalette.ColorRole.Dark))
        zone_color.setAlpha(170 if self.is_live_active else 70)
        painter.setBrush(zone_color)
        painter.drawRoundedRect(zone, _TRACK_HEIGHT / 2, _TRACK_HEIGHT / 2)

        # Опорная отметка
        if self._reference is not None and enabled:
            x = self._x_for(self._reference)
            painter.setPen(QPen(REFERENCE_COLOR, 2))
            painter.drawLine(QPointF(x, track.top() - 4), QPointF(x, track.bottom() + 4))

        # Живой маркер: треугольник над дорожкой
        if self._live is not None and enabled:
            x = self._x_for(self._live)
            color = ACTIVE_COLOR if self.is_live_active else palette.color(QPalette.ColorRole.Text)
            marker = QPainterPath()
            top = track.top() - 3
            marker.moveTo(x, top)
            marker.lineTo(x - _MARKER_HALF_WIDTH, top - 7)
            marker.lineTo(x + _MARKER_HALF_WIDTH, top - 7)
            marker.closeSubpath()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawPath(marker)
            painter.setPen(QPen(color, 2))
            painter.drawLine(QPointF(x, track.top()), QPointF(x, track.bottom()))

        # Ручка порога
        handle_color = palette.color(QPalette.ColorRole.Highlight if enabled else QPalette.ColorRole.Mid)
        painter.setPen(QPen(palette.color(QPalette.ColorRole.Base), 2))
        painter.setBrush(handle_color)
        painter.drawEllipse(QPointF(handle_x, center_y), _HANDLE_RADIUS, _HANDLE_RADIUS)
        if self.hasFocus():
            painter.setPen(QPen(handle_color, 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(handle_x, center_y), _HANDLE_RADIUS + 3, _HANDLE_RADIUS + 3)

    # --- Ввод ---

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.set_value(self._value_at(event.position().x()))

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.set_value(self._value_at(event.position().x()))

    def wheelEvent(self, event):
        # Колесо прокручивает окно, а не меняет порог
        event.ignore()

    def keyPressEvent(self, event: QKeyEvent):
        page = max((self._maximum - self._minimum) // 10, 1)
        steps = {
            Qt.Key.Key_Left: -1,
            Qt.Key.Key_Down: -1,
            Qt.Key.Key_Right: 1,
            Qt.Key.Key_Up: 1,
            Qt.Key.Key_PageDown: -page,
            Qt.Key.Key_PageUp: page,
        }
        if event.key() in steps:
            self.set_value(self._value + steps[event.key()])
        elif event.key() == Qt.Key.Key_Home:
            self.set_value(self._minimum)
        elif event.key() == Qt.Key.Key_End:
            self.set_value(self._maximum)
        else:
            super().keyPressEvent(event)

```

