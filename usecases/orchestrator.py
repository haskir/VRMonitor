from loguru import logger

from consts import BASE_THRESHOLD
from usecases.camera_controller import CameraController
from usecases.cameras_provider import CamerasProvider
from usecases.keyboard_controller import KeyboardController
from usecases.singleton import Singleton
from usecases.windows_provider import WindowsProvider


class Orchestrator(Singleton):
    def __init__(self):
        self.camera_controller: CameraController = CameraController(
            self.on_left, self.on_right, self.on_neutral, BASE_THRESHOLD
        )
        self.camera_provider: CamerasProvider = CamerasProvider()
        self.window_controller: WindowsProvider = WindowsProvider()
        self.keyboard_controller: KeyboardController = KeyboardController()

        self._is_on = False

    def set_camera_view(self, is_visible: bool):
        self.camera_controller.is_visible = is_visible

    def on_left(self):
        if self.window_controller.is_target_active:
            self.keyboard_controller.press_q()

    def on_right(self):
        if self.window_controller.is_target_active:
            self.keyboard_controller.press_e()

    def on_neutral(self):
        if self.window_controller.is_target_active:
            self.keyboard_controller.release_all()

    def set_threshold(self, threshold: int):
        self.camera_controller.threshold = threshold

    def toggle_on_off(self):
        logger.info(f'Orchestrator is {"OFF" if self._is_on else "ON"}')
        if self._is_on:
            self.camera_controller.off()
            self.keyboard_controller.off()
        else:
            self.keyboard_controller.on()
            self.camera_controller.on()
        self._is_on = not self._is_on
        return self._is_on
