from PySide6.QtWidgets import (
    QMainWindow, QApplication, QWidget,
    QVBoxLayout, QPushButton, )

from UI.window_list import WindowSelectWidget
from usecases.windows_provider import WindowsProvider


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