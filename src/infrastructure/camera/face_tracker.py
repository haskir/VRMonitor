from dataclasses import dataclass
from typing import Any

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from domain.pose import Y_SCALE, HeadPose

from .face_model import ensure_face_landmarker

__all__ = ["FaceDetection", "MediaPipeFaceTracker"]


@dataclass(frozen=True, slots=True)
class FaceDetection:
    pose: HeadPose
    landmarks: Any  # Точки лица MediaPipe (нормированные координаты) - для отрисовки сетки


def _head_tilt(landmarks, width: int, height: int) -> float:
    # Внешние уголки глаз; координаты нормированы, поэтому учитываем пропорции кадра
    left_eye, right_eye = landmarks[33], landmarks[263]
    dx = (right_eye.x - left_eye.x) * width
    dy = (right_eye.y - left_eye.y) * height
    return float(np.degrees(np.arctan2(dy, dx)))


class MediaPipeFaceTracker:
    """Находит лицо на кадре и считает позу головы. Не потокобезопасен - используется в потоке камеры"""

    def __init__(self):
        options = vision.FaceLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=str(ensure_face_landmarker())),
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
            num_faces=1,
            # VIDEO-режим отслеживает лицо между кадрами вместо поиска с нуля - быстрее и стабильнее
            running_mode=vision.RunningMode.VIDEO,
        )
        self._detector = vision.FaceLandmarker.create_from_options(options)
        self._last_timestamp_ms = -1

    def detect(self, frame: np.ndarray, timestamp_ms: int) -> FaceDetection | None:
        """frame - BGR-кадр камеры"""
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        # VIDEO-режим требует строго возрастающих меток времени
        timestamp_ms = max(timestamp_ms, self._last_timestamp_ms + 1)
        self._last_timestamp_ms = timestamp_ms
        result = self._detector.detect_for_video(image, timestamp_ms)
        if not result.face_landmarks:
            return None
        landmarks = result.face_landmarks[0]
        height, width = frame.shape[:2]
        pose = HeadPose(tilt=_head_tilt(landmarks, width, height), y=landmarks[0].y * Y_SCALE)
        return FaceDetection(pose=pose, landmarks=landmarks)

    def close(self):
        self._detector.close()
