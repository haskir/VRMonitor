import os
import sys
from PySide6.QtWidgets import QApplication

from UI.main_window import MainWindow

os.chdir(os.path.split(sys.argv[0])[0])


def main():
    try:
        app = QApplication(sys.argv)
        main_window = MainWindow()
        main_window.show()
        sys.exit(app.exec())
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
