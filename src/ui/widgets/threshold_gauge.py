from PySide6.QtCore import QPointF, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QKeyEvent, QMouseEvent, QPainter, QPainterPath, QPalette, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

__all__ = ["ThresholdGauge"]

# Цвет срабатывания: читается и на светлой, и на тёмной теме
ACTIVE_COLOR = QColor("#e8590c")
REFERENCE_COLOR = QColor("#2f9e44")

_HANDLE_RADIUS = 8
_TRACK_HEIGHT = 6
_MARKER_HALF_WIDTH = 5


class ThresholdGauge(QWidget):
    """
    Шкала порога: значение перетаскивается мышью или стрелками, правее порога - зона срабатывания.
    Живой маркер показывает текущее измерение и подсвечивается, когда оно в зоне срабатывания
    """

    value_changed = Signal(int)

    def __init__(self, minimum: int, maximum: int, value: int, parent: QWidget | None = None):
        super().__init__(parent)
        self._minimum = minimum
        self._maximum = maximum
        self._value = self._clamp(value)
        self._live: float | None = None
        self._reference: float | None = None
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def sizeHint(self) -> QSize:
        return QSize(220, 2 * _HANDLE_RADIUS + 14)

    def minimumSizeHint(self) -> QSize:
        return QSize(120, self.sizeHint().height())

    # --- Значения ---

    @property
    def value(self) -> int:
        return self._value

    def set_value(self, value: int, emit: bool = True):
        value = self._clamp(value)
        if value == self._value:
            return
        self._value = value
        self.update()
        if emit:
            self.value_changed.emit(value)

    def set_live(self, value: float | None):
        """Текущее измерение; None - измерения нет"""
        if value != self._live:
            self._live = value
            self.update()

    def set_reference(self, value: float | None):
        """Дополнительная отметка (например, откалиброванный верх головы)"""
        if value != self._reference:
            self._reference = value
            self.update()

    @property
    def is_live_active(self) -> bool:
        return self._live is not None and self._live > self._value

    def _clamp(self, value: float) -> int:
        return int(min(max(round(value), self._minimum), self._maximum))

    # --- Геометрия ---

    def _track_rect(self) -> QRectF:
        left = _HANDLE_RADIUS + 1
        width = self.width() - 2 * left
        return QRectF(left, (self.height() - _TRACK_HEIGHT) / 2, width, _TRACK_HEIGHT)

    def _x_for(self, value: float) -> float:
        track = self._track_rect()
        span = self._maximum - self._minimum or 1
        ratio = (min(max(value, self._minimum), self._maximum) - self._minimum) / span
        return track.left() + ratio * track.width()

    def _value_at(self, x: float) -> int:
        track = self._track_rect()
        ratio = (x - track.left()) / (track.width() or 1)
        return self._clamp(self._minimum + ratio * (self._maximum - self._minimum))

    # --- Отрисовка ---

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self.palette()
        enabled = self.isEnabled()
        track = self._track_rect()
        center_y = track.center().y()
        handle_x = self._x_for(self._value)

        # Дорожка и зона срабатывания правее порога
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(palette.color(QPalette.ColorRole.Mid))
        painter.drawRoundedRect(track, _TRACK_HEIGHT / 2, _TRACK_HEIGHT / 2)
        zone = QRectF(QPointF(handle_x, track.top()), track.bottomRight())
        zone_color = QColor(ACTIVE_COLOR if enabled else palette.color(QPalette.ColorRole.Dark))
        zone_color.setAlpha(170 if self.is_live_active else 70)
        painter.setBrush(zone_color)
        painter.drawRoundedRect(zone, _TRACK_HEIGHT / 2, _TRACK_HEIGHT / 2)

        # Опорная отметка
        if self._reference is not None and enabled:
            x = self._x_for(self._reference)
            painter.setPen(QPen(REFERENCE_COLOR, 2))
            painter.drawLine(QPointF(x, track.top() - 4), QPointF(x, track.bottom() + 4))

        # Живой маркер: треугольник над дорожкой
        if self._live is not None and enabled:
            x = self._x_for(self._live)
            color = ACTIVE_COLOR if self.is_live_active else palette.color(QPalette.ColorRole.Text)
            marker = QPainterPath()
            top = track.top() - 3
            marker.moveTo(x, top)
            marker.lineTo(x - _MARKER_HALF_WIDTH, top - 7)
            marker.lineTo(x + _MARKER_HALF_WIDTH, top - 7)
            marker.closeSubpath()
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawPath(marker)
            painter.setPen(QPen(color, 2))
            painter.drawLine(QPointF(x, track.top()), QPointF(x, track.bottom()))

        # Ручка порога
        handle_color = palette.color(QPalette.ColorRole.Highlight if enabled else QPalette.ColorRole.Mid)
        painter.setPen(QPen(palette.color(QPalette.ColorRole.Base), 2))
        painter.setBrush(handle_color)
        painter.drawEllipse(QPointF(handle_x, center_y), _HANDLE_RADIUS, _HANDLE_RADIUS)
        if self.hasFocus():
            painter.setPen(QPen(handle_color, 1.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(handle_x, center_y), _HANDLE_RADIUS + 3, _HANDLE_RADIUS + 3)

    # --- Ввод ---

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self.set_value(self._value_at(event.position().x()))

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() & Qt.MouseButton.LeftButton:
            self.set_value(self._value_at(event.position().x()))

    def wheelEvent(self, event):
        # Колесо прокручивает окно, а не меняет порог
        event.ignore()

    def keyPressEvent(self, event: QKeyEvent):
        page = max((self._maximum - self._minimum) // 10, 1)
        steps = {
            Qt.Key.Key_Left: -1,
            Qt.Key.Key_Down: -1,
            Qt.Key.Key_Right: 1,
            Qt.Key.Key_Up: 1,
            Qt.Key.Key_PageDown: -page,
            Qt.Key.Key_PageUp: page,
        }
        if event.key() in steps:
            self.set_value(self._value + steps[event.key()])
        elif event.key() == Qt.Key.Key_Home:
            self.set_value(self._minimum)
        elif event.key() == Qt.Key.Key_End:
            self.set_value(self._maximum)
        else:
            super().keyPressEvent(event)
