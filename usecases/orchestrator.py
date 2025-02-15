from PySide6.QtCore import QObject, QTimer
from loguru import logger

from consts import BASE_THRESHOLD
from models import GameSettings
from usecases.camera_controller import CameraController
from usecases.cameras_provider import CamerasProvider
from usecases.keyboard_controller import KeyboardController
from usecases.windows_controller import WindowsController


class Orchestrator(QObject):
    def __init__(self, parent):
        super().__init__(parent)

        self.camera_controller: CameraController = CameraController(
            on_left_callback=self.on_left,
            on_right_callback=self.on_right,
            on_up_callback=self.on_stand,
            on_down_callback=self.on_sit,
            on_neutral_callback=self.on_neutral,
            angle_threshold=BASE_THRESHOLD
        )
        self.camera_provider: CamerasProvider = CamerasProvider()
        self.window_controller: WindowsController = WindowsController()
        self.keyboard_controller: KeyboardController = KeyboardController()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.window_controller.update_current)
        self.timer.start(3000)  # Каждые 3 секунды проверяем активное окно

        self._is_sit_controlling = True

        self._is_on = False

    def update_game_settings(self, settings: GameSettings):
        self.keyboard_controller.set_settings(settings)

    def set_camera_view(self, is_visible: bool):
        self.camera_controller.set_visible(is_visible)

    def on_left(self):
        if self.window_controller.is_target_active:
            self.keyboard_controller.to_left()

    def on_right(self):
        if self.window_controller.is_target_active:
            self.keyboard_controller.to_right()

    def on_neutral(self):
        if self.window_controller.is_target_active:
            self.keyboard_controller.release_all()

    def set_is_sit_controlling(self, is_sit_controlling: bool):
        logger.info("Включение приседаний" if is_sit_controlling else "Выключение приседаний")
        self._is_sit_controlling = is_sit_controlling
        self.camera_controller.set_sit_mode(is_sit_controlling)

    def on_sit(self):
        print("on_sit")
        if not self._is_sit_controlling:
            return
        if not self.window_controller.is_target_active:
            return
        self.keyboard_controller.sit()

    def on_stand(self):
        print("on_stand")
        if not self._is_sit_controlling:
            return
        if not self.window_controller.is_target_active:
            return
        self.keyboard_controller.stand()

    def set_threshold(self, threshold: int):
        self.camera_controller.angle_threshold = threshold

    def toggle_on_off(self):
        logger.info(f'Orchestrator is {"OFF" if self._is_on else "ON"}')
        self._is_on = not self._is_on
        if self._is_on:
            self.camera_controller.on()
        else:
            self.camera_controller.off()