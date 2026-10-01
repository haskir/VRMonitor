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
