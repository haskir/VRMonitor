from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QMainWindow, QApplication, QWidget,
    QVBoxLayout, QPushButton, QRadioButton,
    QButtonGroup,
)
from pygetwindow import Win32Window

from windows_provider import WindowsProvider


class WindowRadioButton(QRadioButton):
    def __init__(self, parent, window: Win32Window | None):
        super().__init__(parent)
        self._window = window
        self.update()

    def update(self):
        self.setText("Все окна") if self._window is None else self.setText(self._window.title)
        super().update()


class WindowSelectWidget(QWidget):
    def __init__(self, parent, windows_provider: WindowsProvider):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)

        self._windows: dict[str, Win32Window | None] = {"None": None}
        self._windows_provider = windows_provider

        self._radio_buttons: list[WindowRadioButton] = list()
        self._radio_buttons_layout = QVBoxLayout()
        self._group = QButtonGroup(self)
        self._update_window_list()

        self.layout.addLayout(self._radio_buttons_layout)

        # Таймер для обновления списка окон
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_window_list)
        self._timer.start(5000)  # Интервал обновления - 5 секунд

    def _get_windows(self):
        updated_list = self._windows_provider.all_windows()
        for hWnd, window in updated_list.items():
            if hWnd not in self._windows:
                self._windows[hWnd] = window
                self._group.removeButton(b)
                b.deleteLater()
            else:
                self._windows[hWnd].title = window.title
        for b in self._radio_buttons:
        self._radio_buttons.clear()

    def add_window(self, window: Win32Window):
        rb = WindowRadioButton(self, window)
        rb.clicked.connect(self.on_select)
        self._group.addButton(rb)
        self._radio_buttons_layout.addWidget(rb)
        self._radio_buttons.append(rb)

    def _update_window_list(self):
        self._get_windows()
        self._windows.sort(key=lambda w: w.title)
        for window in self._windows:
            self.add_window(window)

    @classmethod
    def on_select(cls, *args):
        print(args)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Window Selector")

        self.central_widget = QWidget(self)
        self.setCentralWidget(self.central_widget)

        self.layout = QVBoxLayout(self.central_widget)

        # Кнопка для включения/выключения таймера
        self.toggle_button = QPushButton("Вкл", self)
        self.toggle_button.setCheckable(True)
        self.toggle_button.toggled.connect(self.toggle_timer)

        # Виджет выбора окна
        self.window_select_widget = WindowSelectWidget(self, WindowsProvider())

        self.layout.addWidget(self.window_select_widget)
        self.layout.addWidget(self.toggle_button)

    def toggle_timer(self, checked):
        if checked:
            self.toggle_button.setText("Выкл")
        else:
            self.toggle_button.setText("Вкл")


if __name__ == "__main__":
    import sys

    app = QApplication(sys.argv)

    main_window = MainWindow()
    main_window.show()

    sys.exit(app.exec())
