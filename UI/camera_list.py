from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
)

from UI.pointed_combo_box import PointedComboBox
from usecases.cameras_provider import CamerasProvider
from usecases.camera_controller import CameraController


class CameraSelectWidget(QWidget):
    def __init__(
            self, parent,
            camera_provider: CamerasProvider,
            camera_controller: CameraController
    ):
        super().__init__(parent)

        self._camera_provider = camera_provider
        self._camera_controller = camera_controller

        self.layout = QVBoxLayout(self)

        self.camera_box = PointedComboBox(self)
        self.camera_box.currentIndexChanged.connect(self.on_select)
        self.layout.addWidget(self.camera_box)

        self._update_camera_list()

    def _update_camera_list(self):
        self.camera_box.add_items(self._camera_provider.get_available_cameras())

    def on_select(self):
        """ Сигнализирует об изменении камеры """
        self._camera_controller.set_camera_index(self.current_camera_index)

    @property
    def current_camera_index(self) -> int:
        return self.camera_box.current_data.index
