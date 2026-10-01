"""Заглушки портов для тестов"""

from application.events import Event
from domain.camera import CameraInfo, CameraMode
from domain.pose import Stance
from domain.settings import AppSettings


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float):
        self.now = round(self.now + seconds, 6)


class RecordingKeySender:
    def __init__(self):
        self.events: list[tuple[str, str]] = []

    def key_down(self, button: str):
        self.events.append(("down", button))

    def key_up(self, button: str):
        self.events.append(("up", button))

    def tap(self, button: str):
        self.events.append(("tap", button))


class FakeGameWindow:
    def __init__(self, active: bool = True):
        self.active = active

    def is_game_active(self) -> bool:
        return self.active

    def foreground_rect(self):
        return (0, 0, 2560, 1440)


class ToggleCrouchGame:
    """
    Игра с приседом-переключателем: C меняет стоя <-> сидя, из положения лёжа - в присед.
    Иконка в HUD обновляется с задержкой (анимация)
    """

    def __init__(self, clock: FakeClock, icon_delay: float = 0.4):
        self._clock = clock
        self._icon_delay = icon_delay
        self.stance = Stance.STAND
        self._icon_changes: list[tuple[float, Stance]] = []
        self.taps = 0

    def set_stance(self, stance: Stance):
        self.stance = stance
        self._icon_changes.append((self._clock.now + self._icon_delay, stance))

    def key_down(self, button: str):
        pass

    def key_up(self, button: str):
        pass

    def tap(self, button: str):
        if button.lower() != "c":
            return
        self.taps += 1
        self.set_stance(Stance.STAND if self.stance == Stance.CROUCH else Stance.CROUCH)

    def detect(self, rect) -> Stance | None:
        shown = Stance.STAND
        for at, stance in self._icon_changes:
            if at <= self._clock.now:
                shown = stance
        return shown


class MemorySettingsRepository:
    def __init__(self, settings: AppSettings | None = None):
        self.settings = settings or AppSettings()
        self.saved: list[AppSettings] = []

    def load(self) -> AppSettings:
        return self.settings

    def save(self, settings: AppSettings):
        self.saved.append(settings)


class FakeCameraCatalog:
    def list_cameras(self) -> list[CameraInfo]:
        return [CameraInfo(index=1, name="Webcam", modes=[CameraMode(1280, 720, 60, "MJPG")])]


class RecordingCameraRuntime:
    def __init__(self):
        self.virtual_cam_failed: Event[str] = Event()
        self.calls: list[tuple[str, object]] = []
        self.running = False

    def start(self):
        self.running = True

    def stop(self, wait: bool = False):
        self.running = False

    def __getattr__(self, name: str):
        if name.startswith("set_"):
            return lambda value: self.calls.append((name, value))
        raise AttributeError(name)
