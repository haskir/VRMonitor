from typing import Any

from PySide6.QtCore import QObject
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QComboBox, QWidget

__all__ = ["PointedComboBox"]

TOOLTIP_LINE_LENGTH = 50


class PointedComboBox(QComboBox):
    """Выпадающий список, где у каждого пункта есть объект данных (подпись - его repr)"""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setMaxVisibleItems(10)
        self._model = QStandardItemModel()
        self.setModel(self._model)
        self.currentIndexChanged.connect(self._update_tooltip)

    def _update_tooltip(self):
        # Длинные названия камер переносим по словам
        lines, line = [], ""
        for word in self.currentText().split(" "):
            if line and len(line) + len(word) > TOOLTIP_LINE_LENGTH:
                lines.append(line.strip())
                line = ""
            line += word + " "
        lines.append(line.strip())
        self.setToolTip("\n".join(lines))

    def add_items(self, items: list, add_empty: tuple[bool, str] = (False, "")):
        if add_empty[0]:
            item = QStandardItem(add_empty[1])
            item.setData(None)
            self._model.appendRow(item)
        for data in items:
            item = QStandardItem(repr(data))
            item.setData(data)
            self._model.appendRow(item)
        if self._model.rowCount():
            self.setCurrentIndex(0)

    @property
    def current_data(self) -> Any:
        item = self._model.item(self.currentIndex())
        if item:
            return item.data()
        return None

    def wheelEvent(self, event):
        # Прокрутка колесом не должна случайно переключать камеру - отдаём её родителю
        parent: QObject | None = self.parent()
        if isinstance(parent, QWidget):
            parent.wheelEvent(event)
