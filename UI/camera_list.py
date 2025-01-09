from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget, QHBoxLayout, QToolButton, QStyle
from loguru import logger

from UI.pointed_combo_box import PointedComboBox
from usecases.cameras_provider import CameraProvider


class CameraSelectWidget(QWidget):
    new_camera_selected = Signal(int)

    def __init__(self, parent, camera_controller: CameraProvider):
        super().__init__(parent)

        self._camera_controller = camera_controller

        self.layout = QHBoxLayout(self)
        self.camera_box = PointedComboBox(self)
        self.camera_box.currentIndexChanged.connect(self.on_select)

        self.toggle_button = QToolButton(self)
        self.toggle_button.clicked.connect(self._toggle_view)
        self._is_camera_visible = True

        self.layout.addWidget(self.camera_box)
        self.layout.addWidget(self.toggle_button)

        self._toggle_view()
        self._update_camera_list()

    def _toggle_view(self):
        if self._is_camera_visible:
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowUp)
        else:
            icon = self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown)
        self.toggle_button.setIcon(icon)
        self._is_camera_visible = not self._is_camera_visible
        ...

    def _update_camera_list(self):
        self.camera_box.add_items(self._camera_controller.get_available_cameras())

    def on_select(self):
        self.new_camera_selected.emit(self.camera_box.current_data.index)

    @property
    def current_camera_index(self) -> int:
        return self.camera_box.current_data.index
