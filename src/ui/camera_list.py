from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from domain.camera import CameraInfo, CameraMode
from ui.pointed_combo_box import PointedComboBox

__all__ = ["CameraSelectWidget"]

DEFAULT_MODE_TITLE = "Режим по умолчанию"


class CameraSelectWidget(QWidget):
    camera_changed = Signal(int)
    mode_changed = Signal(object)  # CameraMode | None

    def __init__(self, parent: QWidget, cameras: list[CameraInfo]):
        super().__init__(parent)

        self._layout: QVBoxLayout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        self.camera_box = PointedComboBox(self)
        self.camera_box.currentIndexChanged.connect(self._on_camera_select)
        self._layout.addWidget(self.camera_box)

        self.mode_box = PointedComboBox(self)
        self.mode_box.setToolTip("Разрешение и частота кадров камеры")
        self.mode_box.currentIndexChanged.connect(self._on_mode_select)
        self._layout.addWidget(self.mode_box)

        self.camera_box.add_items(cameras)

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

    def _update_mode_list(self, camera: CameraInfo | None):
        self.mode_box.blockSignals(True)
        self.mode_box.clear()
        self.mode_box.add_items(camera.modes if camera else [], add_empty=(True, DEFAULT_MODE_TITLE))
        self.mode_box.blockSignals(False)
        self._on_mode_select()

    def _on_camera_select(self):
        camera: CameraInfo | None = self.camera_box.current_data
        self._update_mode_list(camera)
        if camera:
            self.camera_changed.emit(camera.index)

    def _on_mode_select(self):
        self.mode_changed.emit(self.mode_box.current_data)

    @property
    def current_camera_index(self) -> int | None:
        camera: CameraInfo | None = self.camera_box.current_data
        return camera.index if camera else None

    @property
    def current_mode(self) -> CameraMode | None:
        return self.mode_box.current_data
