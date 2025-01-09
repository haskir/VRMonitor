from PySide6.QtCore import QTimer, Signal, Qt
from PySide6.QtWidgets import QCheckBox, QWidget, QVBoxLayout, QButtonGroup, QLabel, QScrollArea, QHBoxLayout
from loguru import logger

from usecases.windows_provider import WindowsProvider, CustomWin32Window


class WindowRadioButton(QCheckBox):
    selected_signal = Signal(int, bool)

    def __init__(self, parent, window: CustomWin32Window | None):
        super().__init__(parent)

        self.window: CustomWin32Window = window
        self.update()

        self.toggled.connect(self.on_clicked)

    def update(self):
        try:
            self.setText("Все окна") if self.window is None else self.setText(self.window.title)
            super().update()
        except Exception as e:
            logger.error(f"Ошибка при обновлении строки с [{self.text()}]: {e}")

    def on_clicked(self) -> (int, bool):
        self.selected_signal.emit(self.window.hWnd if self.window else -1, self.isChecked())


class WindowSelectWidget(QWidget):
    def __init__(self, parent, windows_provider: WindowsProvider):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)

        self._windows: dict[int, WindowRadioButton] = dict()
        self._windows_provider = windows_provider

        # Заголовок
        self.top_layout = QHBoxLayout()

        self.title = QLabel("Окна, в которых работает программа", self)
        self.title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._all_toggler = QCheckBox("Все окна", self)
        self._all_toggler.stateChanged.connect(self._toggle_all)

        self.top_layout.addWidget(self.title)
        self.top_layout.addWidget(self._all_toggler)

        self.layout.addLayout(self.top_layout)

        # Область с прокруткой
        self.scroll_area = QScrollArea(self)
        self.scroll_area.setWidgetResizable(True)  # Разрешаем подгонку под содержимое
        self.layout.addWidget(self.scroll_area)

        # Контейнер для кнопок внутри прокручиваемой области
        self.scroll_content = QWidget(self.scroll_area)
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_content.setLayout(self.scroll_layout)
        self.scroll_area.setWidget(self.scroll_content)

        # Таймер для обновления списка окон
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._get_windows)
        self._timer.start(5000)  # Интервал обновления - 5 секунд

        # Заполняем список окон
        self._get_windows()

    def add_window(self, window: CustomWin32Window):
        rb = WindowRadioButton(self, window)
        rb.selected_signal.connect(self._on_clicked)
        self.scroll_layout.addWidget(rb)
        self._windows[window.hWnd] = rb

    def _get_windows(self):
        updated_list = self._windows_provider.all_windows()
        for window in updated_list:
            if window.hWnd not in self._windows:
                self.add_window(window)
        for hwnd, widget in self._windows.copy().items():
            if widget.window not in updated_list:
                logger.debug(f"Удаление строки [{widget.text()}]")
                self.remove_window(hwnd)

    def remove_window(self, window: int):
        rb: WindowRadioButton = self._windows.pop(window)
        self.scroll_layout.removeWidget(rb)
        rb.deleteLater()

    def _on_clicked(self, hwnd: int, checked: bool):
        if checked:
            self._windows_provider.add_window(self._windows[hwnd].window)
        else:
            self._windows_provider.remove_window(self._windows[hwnd].window)

    def _toggle_all(self, checked: bool):
        self._windows_provider.is_all_targets = checked
        self.scroll_content.setEnabled(not checked)

    @classmethod
    def on_select(cls, *args):
        print(args)
