import os
import sys
from pprint import pprint

import cv2
from PySide6.QtWidgets import QApplication

from UI.main_page import MainWindow
from usecases import cameras_provider
from usecases.camera_controller import CameraController
from usecases.keyboard_controller import KeyboardController
from usecases.windows_provider import WindowsProvider

os.chdir(os.path.split(sys.argv[0])[0])


def main_without_ui():
    cameras = cameras_provider.CameraProvider.get_available_cameras_ids()
    if not cameras:
        exit("Нет доступных камер.")
    print(f"Доступные камеры: {cameras}")
    cap = cv2.VideoCapture(cameras[0])

    window_finder = WindowsProvider()
    windows = window_finder.all_windows()
    pprint(windows)
    # inp = int(input(f"Выберите окно: от -1 до {len(windows) - 1}\n"))
    inp = -1
    for i, window in windows.items():
        if "Элитный чат" in window.title:
            inp = i
    window_finder.add_window(windows.get(inp))

    camera_controller = CameraController(cap, KeyboardController(), THRESHOLD, window_finder)
    camera_controller.run()
    cap.release()
    cv2.destroyAllWindows()


def main_UI():
    app = QApplication(sys.argv)
    main_window = MainWindow()
    main_window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    THRESHOLD: int = 16
    main_UI()
