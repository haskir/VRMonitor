"""Отрисовка поверх кадра камеры: сетка лица, линии приседа, подпись"""

import cv2
import numpy as np
from mediapipe.tasks.python.vision import FaceLandmarksConnections

from application.head_tracking import TrackingOverlay
from domain.pose import Y_SCALE

__all__ = ["draw_face_mesh", "draw_sit_lines", "draw_status"]

# Пары индексов точек, образующие рёбра сетки лица
FACE_MESH_EDGES = np.array([(c.start, c.end) for c in FaceLandmarksConnections.FACE_LANDMARKS_TESSELATION])


def draw_face_mesh(frame: np.ndarray, landmarks):
    height, width = frame.shape[:2]
    points = np.array([(lm.x * width, lm.y * height) for lm in landmarks], dtype=np.int32)
    # Все рёбра сетки одним вызовом - на порядок быстрее, чем рисовать их по одному
    cv2.polylines(frame, list(points[FACE_MESH_EDGES]), False, (0, 255, 255), 1, cv2.LINE_AA)


def draw_sit_lines(frame: np.ndarray, overlay: TrackingOverlay):
    """Зелёная линия - откалиброванный верх головы, красная - порог приседа"""
    if not overlay.sit_enabled:
        return
    height, width = frame.shape[:2]
    if overlay.base_y is not None:
        base_px = int(overlay.base_y * height / Y_SCALE)
        cv2.line(frame, (0, base_px), (width, base_px), (0, 255, 0), 1)
    threshold_px = int(overlay.sit_threshold * height / Y_SCALE)
    cv2.line(frame, (0, threshold_px), (width, threshold_px), (0, 0, 255), 2)


def _tilt_text(tilt: float, threshold: float) -> str:
    if tilt > 10:
        return f"Head tilt to the left ({tilt:.2f}) [{threshold}]"
    if tilt < -10:
        return f"Head tilt to the right ({tilt:.2f}) [{threshold}]"
    return f"Head is straight ({tilt:.2f}) [{threshold}]"


def draw_status(frame: np.ndarray, tilt: float, overlay: TrackingOverlay, fps: float):
    cv2.putText(
        frame,
        text=f"{_tilt_text(tilt, overlay.angle_threshold)} {fps:.0f} fps",
        org=(10, 30),
        fontFace=cv2.FONT_HERSHEY_SIMPLEX,
        fontScale=0.7,
        color=(255, 0, 0),
    )
