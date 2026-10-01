from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from models import CameraMode
from ui.pointed_combo_box import PointedComboBox
from usecases.camera_controller import CameraController
from usecases.cameras_provider import Camera, CamerasProvider

__all__ = ["CameraSelectWidget"]

DEFAULT_MODE_TITLE = "Режим по умолчанию"


class CameraSelectWidget(QWidget):
    camera_changed = Signal(int)
    mode_changed = Signal(object)  # CameraMode | None

    def __init__(
        self,
        parent: QWidget,
        camera_provider: CamerasProvider,
        camera_controller: CameraController,
    ):
        super().__init__(parent)

        self._camera_provider = camera_provider
        self._camera_controller = camera_controller

        self._layout: QVBoxLayout = QVBoxLayout(self)
        self.setLayout(self._layout)

        self.camera_box = PointedComboBox(self)
        self.camera_box.currentIndexChanged.connect(self.on_select)
        self._layout.addWidget(self.camera_box)

        self.mode_box = PointedComboBox(self)
        self.mode_box.setToolTip("Разрешение и частота кадров камеры")
        self.mode_box.currentIndexChanged.connect(self.on_mode_select)
        self._layout.addWidget(self.mode_box)

        self._update_camera_list()

    @staticmethod
    def _find_row(box: PointedComboBox, predicate) -> int | None:
        for row in range(box.count()):
            data = box.itemData(row, Qt.ItemDataRole.UserRole + 1)
            if data and predicate(data):
                return row
        return None

    def select_camera(self, index: int):
        """Выбирает камеру по её системному индексу, если она доступна"""
        row = self._find_row(self.camera_box, lambda camera: camera.index == index)
        if row is not None:
            self.camera_box.setCurrentIndex(row)

    def select_mode(self, mode: CameraMode | None):
        """Выбирает режим текущей камеры; если камера его не поддерживает - режим по умолчанию"""
        row = self._find_row(self.mode_box, lambda m: m == mode) if mode else None
        self.mode_box.setCurrentIndex(row if row is not None else 0)

    def _update_camera_list(self):
        self.camera_box.add_items(self._camera_provider.get_available_cameras())

    def _update_mode_list(self, camera: Camera | None):
        self.mode_box.blockSignals(True)
        self.mode_box.clear()
        self.mode_box.add_items(camera.modes if camera else [], add_empty=(True, DEFAULT_MODE_TITLE))
        self.mode_box.blockSignals(False)
        self.on_mode_select()

    def on_select(self):
        """Сигнализирует об изменении камеры"""
        camera: Camera | None = self.camera_box.current_data
        self._update_mode_list(camera)
        if camera:
            self._camera_controller.set_camera_index(camera.index)
            self.camera_changed.emit(camera.index)

    def on_mode_select(self):
        mode: CameraMode | None = self.mode_box.current_data
        self._camera_controller.set_camera_mode(mode)
        self.mode_changed.emit(mode)

    @property
    def current_camera_index(self) -> int | None:
        camera: Camera | None = self.camera_box.current_data
        return camera.index if camera else None

    @property
    def current_mode(self) -> CameraMode | None:
        return self.mode_box.current_data
