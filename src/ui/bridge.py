from PySide6.QtCore import QObject, QTimer, Signal

from application.app import App
from consts import POLL_INTERVAL_MS

__all__ = ["QtBridge"]

SAVE_DELAY_MS = 500


class QtBridge(QObject):
    """
    Связь App с Qt: события приложения (в т.ч. из потока камеры) приходят сюда в поток GUI
    через очередь событий Qt; таймеры опрашивают окно игры и сохраняют настройки
    """

    game_active_changed = Signal(bool)
    stance_changed = Signal(object)  # Stance | None
    calibrated = Signal(int)
    virtual_cam_failed = Signal(str)

    def __init__(self, app: App, parent: QObject | None = None):
        super().__init__(parent)
        self._app = app

        app.game_active_changed.connect(self.game_active_changed.emit)
        app.stance_changed.connect(self.stance_changed.emit)
        app.calibrated.connect(self.calibrated.emit)
        app.virtual_cam_failed.connect(self.virtual_cam_failed.emit)

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(app.poll)
        self._poll_timer.start(POLL_INTERVAL_MS)

        # Настройки сохраняются с небольшой задержкой, чтобы не писать файл на каждый шаг слайдера
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(SAVE_DELAY_MS)
        self._save_timer.timeout.connect(app.save)
        app.settings_changed.connect(lambda _: self._save_timer.start())

    def shutdown(self):
        self._poll_timer.stop()
        self._save_timer.stop()
        self._app.shutdown()
