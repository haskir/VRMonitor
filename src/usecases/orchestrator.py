import threading
import time

from loguru import logger
from PySide6.QtCore import QObject, QTimer, Signal

from consts import BASE_THRESHOLD, STANCE_SETTLE_SECONDS, WINDOW_CHECK_INTERVAL_MS
from models import GameSettings
from usecases.camera_controller import CameraController
from usecases.cameras_provider import CamerasProvider
from usecases.keyboard_controller import KeyboardController
from usecases.stance_detector import Stance, StanceDetector, StanceTracker
from usecases.windows_controller import WindowsController


class Orchestrator(QObject):
    # Испускается из потока камеры, в GUI доставляется через очередь событий Qt
    y_threshold_calibrated = Signal(int)
    virtual_cam_failed = Signal(str)
    # Игра появилась/пропала на переднем плане
    game_active_changed = Signal(bool)
    # Поза персонажа по HUD игры (Stance | None)
    stance_changed = Signal(object)

    def __init__(self, parent, game_settings: GameSettings | None = None):
        super().__init__(parent)

        self.camera_controller: CameraController = CameraController(
            on_left_callback=self.on_left,
            on_right_callback=self.on_right,
            on_up_callback=self.on_stand,
            on_down_callback=self.on_sit,
            on_neutral_callback=self.on_neutral,
            angle_threshold=BASE_THRESHOLD,
            on_calibrated_callback=self.y_threshold_calibrated.emit,
            on_virtual_cam_error_callback=self.virtual_cam_failed.emit,
        )
        self.camera_provider: CamerasProvider = CamerasProvider()
        self.window_controller: WindowsController = WindowsController()
        self.keyboard_controller: KeyboardController = KeyboardController(game_settings)

        self._is_sit_controlling: bool = True
        self._is_on: bool = False

        # Что делает голова прямо сейчас; на клавиатуру применяется, только пока активна игра
        self._desired_lean: str | None = None
        self._desired_sit: bool | None = None  # None - ещё неизвестно
        # Клавиши жмутся и из потока камеры, и из таймера окон
        self._lock = threading.RLock()
        self._target_active: bool = False
        self._game_active: bool = False

        # Поза персонажа в игре: лёжа приседания с камеры не применяются
        self._detect_stance: bool = True
        self._stance_detector = StanceDetector()
        self._stance_tracker = StanceTracker()

        self.timer: QTimer = QTimer(self)
        self.timer.timeout.connect(self._check_active_window)
        self.timer.start(WINDOW_CHECK_INTERVAL_MS)

    def update_game_settings(self, settings: GameSettings):
        with self._lock:
            self.keyboard_controller.set_settings(settings)

    def set_camera_view(self, is_visible: bool):
        self.camera_controller.set_visible(is_visible)

    def set_only_in_game(self, only_in_game: bool):
        logger.info("Клавиши нажимаются только в игре" if only_in_game else "Клавиши нажимаются в любом окне")
        self.window_controller.is_all_targets = not only_in_game
        self._sync()

    def _check_active_window(self):
        game_active = self.window_controller.is_game_active
        if game_active != self._game_active:
            self._game_active = game_active
            logger.info(f"Игра {'на переднем плане' if game_active else 'не в фокусе'}")
            self.game_active_changed.emit(game_active)
        self._update_stance()
        self._sync()

    def set_detect_stance(self, detect_stance: bool):
        logger.info("Поза в игре учитывается" if detect_stance else "Поза в игре не учитывается")
        self._detect_stance = detect_stance
        self._update_stance()

    def _update_stance(self):
        """Снимает иконку позы с HUD, пока игра на переднем плане и детекция включена"""
        tracker = self._stance_tracker
        if not (self._detect_stance and self._is_on and self._game_active):
            with self._lock:
                changed = tracker.reset()
            if changed:
                self._on_stance_changed(tracker.stance)
            return

        reading = None
        # Время снимка берём до него: нажатие из потока камеры могло случиться, пока снимали экран
        timestamp = time.monotonic()
        rect = self.window_controller.foreground_client_rect()
        if rect:
            try:
                reading = self._stance_detector.detect(rect)
            except Exception as e:
                logger.error(f"Не удалось определить позу персонажа: {e}")
        with self._lock:
            changed = tracker.update(reading, timestamp)
            # Игра - источник истины: если игрок сам сменил позу, принимаем её, а _sync приведёт к камере
            if (
                tracker.is_settled
                and tracker.stance in (Stance.STAND, Stance.CROUCH)
                and self.keyboard_controller.assume_sitting(tracker.stance == Stance.CROUCH)
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
            target_active = self.window_controller.is_target_active
            keyboard = self.keyboard_controller
            if not target_active:
                if self._target_active:
                    # Ушли из игры - отпускаем зажатые клавиши, чтобы они не "залипли" в других окнах
                    keyboard.release_held()
                self._target_active = False
                return
            self._target_active = True

            if self._desired_lean != keyboard.current_lean:
                if self._desired_lean == "left":
                    keyboard.to_left()
                elif self._desired_lean == "right":
                    keyboard.to_right()
                else:
                    keyboard.release_all()

            is_prone = self._stance_tracker.stance == Stance.PRONE
            if (
                self._is_sit_controlling
                and not is_prone
                and self._desired_sit is not None
                and self._desired_sit != keyboard.is_sitting
            ):
                if self._desired_sit:
                    keyboard.sit()
                else:
                    keyboard.stand()
                # Пока идёт анимация, иконка показывает старую позу - не принимаем её за истину
                self._stance_tracker.ignore_until(time.monotonic() + STANCE_SETTLE_SECONDS)

    def on_left(self):
        self._desired_lean = "left"
        self._sync()

    def on_right(self):
        self._desired_lean = "right"
        self._sync()

    def on_neutral(self):
        self._desired_lean = None
        self._sync()

    def set_is_sit_controlling(self, is_sit_controlling: bool):
        logger.info("Включение приседаний" if is_sit_controlling else "Выключение приседаний")
        self._is_sit_controlling = is_sit_controlling
        self.camera_controller.set_sit_mode(is_sit_controlling)

    def on_sit(self):
        self._desired_sit = True
        self._sync()

    def on_stand(self):
        self._desired_sit = False
        self._sync()

    def set_threshold(self, threshold: int):
        self.camera_controller.angle_threshold = threshold

    def toggle_on_off(self):
        logger.info(f"Orchestrator is {'OFF' if self._is_on else 'ON'}")
        self._is_on = not self._is_on
        if self._is_on:
            self.camera_controller.on()
        else:
            self.camera_controller.off()
            # Детекция выключена - голова "в нейтрали", отпускаем наклон
            self._desired_lean = None
            self._sync()

    @property
    def is_game_active(self) -> bool:
        return self._game_active

    @property
    def stance(self) -> Stance | None:
        return self._stance_tracker.stance
