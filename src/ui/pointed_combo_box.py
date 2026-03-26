from typing import Any

from PySide6.QtCore import QObject, Qt
from PySide6.QtGui import QKeyEvent, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import QApplication, QComboBox, QCompleter, QWidget

__all__ = ["PointedComboBox"]


class PointedComboBox(QComboBox):
    def __init__(
        self,
        parent: QWidget,
        items: list | None = None,
        editable: bool = False,
        add_empty: tuple[bool, str] = (False, ""),
    ):
        super().__init__(parent)
        self.setEditable(editable)
        if editable:
            completer: QCompleter | None = self.completer()
            if completer:
                completer.setFilterMode(Qt.MatchFlag.MatchContains)
                completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self.setMaxVisibleItems(10)
        self._model = QStandardItemModel()
        self.setModel(self._model)
        if items:
            self.add_items(items, add_empty)
        self.currentIndexChanged.connect(self.updateTooltip)

    def updateTooltip(self):
        max_length = 50
        words = self.currentText().split(" ")
        wrapped_lines = []

        current_line = ""
        for word in words:
            if len(current_line) + len(word) > max_length:
                wrapped_lines.append(current_line.strip())
                current_line = word + " "
            else:
                current_line += word + " "
        wrapped_lines.append(current_line.strip())  # Добавляем последнюю строку

        self.setToolTip("\n".join(wrapped_lines))

    def add_items(self, points: list, add_empty=(False, "")):
        if add_empty[0]:
            item = QStandardItem(add_empty[1])
            item.setData(None)  # Устанавливаем пользовательские данные
            self._model.appendRow(item)
        for point in points:
            item = QStandardItem(repr(point))
            item.setData(point)  # Устанавливаем пользовательские данные
            self._model.appendRow(item)
        if add_empty:
            self.setCurrentIndex(0)

    def is_ready(self) -> bool:
        return bool(self.current_data)

    def setCurrentItem(self, target: int):
        for index in range(self._model.rowCount()):
            item = self._model.item(index)
            if not item.data():
                continue
            if item.data().id == target or item.data() == target:
                self.setCurrentIndex(index)
                break
        if self.isEditable():
            key_event = QKeyEvent(QKeyEvent.Type.KeyPress, Qt.Key.Key_Home, Qt.KeyboardModifier.NoModifier)
            QApplication.postEvent(self, key_event)

    @property
    def current_id(self) -> int | None:
        if self.current_data:
            return self.current_data.id
        return None

    @property
    def current_data(self) -> Any:
        item = self._model.item(self.currentIndex())
        if item:
            return item.data()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Enter, Qt.Key.Key_Return):
            if self.findText(self.currentText()) != -1:
                return
            return
        else:
            super().keyPressEvent(event)

    def wheelEvent(self, event):
        parent: QObject | None = self.parent()
        if isinstance(parent, QWidget):
            parent.wheelEvent(event)
