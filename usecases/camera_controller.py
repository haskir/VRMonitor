import time
from typing import Callable
from venv import logger

import cv2
import mediapipe as mp
import numpy as np

from consts import TEST_CAMERA_TITLE


class CameraController:
    def __init__(
            self,
            on_left: Callable,
            on_right: Callable,
            on_neutral: Callable,
            threshold: int
    ):
        self.on_left = on_left
        self.on_right = on_right
        self.on_neutral = on_neutral
        self.threshold = threshold
        self.camera_index = 0
        self.is_on = False
        self.visualize_detection = True

        self.is_visible = False
        self.cap = None

    def on(self):
        if not self.is_on:
            self.is_on = True
            self._run()

    def off(self):
        self.is_on = False

    def set_camera_index(self, index: int):
        self.camera_index = index

    def _get_text_to_display(self, angle: float) -> str:
        # Определение направления наклона
        if angle > 10:
            return f"Head tilt to the left ({angle:.2f}) [{self.threshold}]"
        elif angle < -10:
            return f"Head tilt to the right ({angle:.2f}) [{self.threshold}]"
        else:
            return f"Head is straight ({angle:.2f}) [{self.threshold}]"

    @classmethod
    def _put_text_to_window(cls, text: str, frame, color: tuple[int, int, int] = None):
        """
        Функция для отображения направления наклона на экране
        """
        cv2.putText(
            frame,
            text=text,
            org=(10, 30),
            fontFace=cv2.FONT_HERSHEY_SIMPLEX,
            fontScale=0.7,
            color=color if color else (255, 255, 255)
        )

    @classmethod
    def _calculate_head_tilt(cls, landmarks):
        """
        Функция для вычисления угла наклона головы
        """
        # Координаты глаз
        left_eye = np.array([(landmarks[33][0], landmarks[33][1])])  # Левый глаз
        right_eye = np.array([(landmarks[263][0], landmarks[263][1])])  # Правый глаз

        # Вычисление угла между глазами
        dx = right_eye[0][0] - left_eye[0][0]
        dy = right_eye[0][1] - left_eye[0][1]
        angle = np.degrees(np.arctan2(dy, dx))
        return angle

    @classmethod
    def _visualize_face(cls, frame, landmarks):
        """
        Функция для отображения глаз на изображении. Визуализация точек лица
        """
        for x, y in landmarks:
            cv2.circle(
                frame,
                center=(int(x), int(y)),
                radius=1,
                color=(0, 255, 255),
                thickness=-1)

    def _is_sufficient_angle(self, angle: float) -> bool:
        return abs(angle) > self.threshold

    def _run(self):
        logger.info(f'Запуск камеры {self.camera_index}')

        # Инициализация Mediapipe
        mp_face_mesh = mp.solutions.face_mesh
        face_mesh = mp_face_mesh.FaceMesh()

        self.cap = cv2.VideoCapture(self.camera_index)

        is_destroyed = False
        is_created = False

        while self.cap.isOpened() and self.is_on:
            time.sleep(0.03)
            try:
                ret, frame = self.cap.read()
                if not ret:
                    break
                # Преобразуем изображение в RGB (требуется Mediapipe)
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Обнаружение лица
                results = face_mesh.process(rgb_frame)

                if results.multi_face_landmarks:
                    for face_landmarks in results.multi_face_landmarks:
                        # Извлечение координат ключевых точек лица
                        landmarks = [(lm.x * frame.shape[1], lm.y * frame.shape[0])
                                     for lm in face_landmarks.landmark]
                        # Вычисление угла наклона
                        angle = self._calculate_head_tilt(landmarks)

                        if self._is_sufficient_angle(angle):
                            self.on_left() if angle > 0 else self.on_right()
                        else:
                            self.on_neutral()

                        if not self.is_visible:
                            continue

                        self._put_text_to_window(
                            self._get_text_to_display(angle),
                            frame,
                            (255, 0, 0)  # Blue
                        )

                        if self.visualize_detection:
                            self._visualize_face(frame, landmarks)

                # Показываем изображение
                if self.is_visible:
                    cv2.imshow(TEST_CAMERA_TITLE, frame)
                    is_created = True
                elif is_created and not is_destroyed:
                    cv2.destroyWindow(TEST_CAMERA_TITLE)
                    is_destroyed = True

                # Выход из программы по нажатию клавиши "]"
                if cv2.waitKey(1) & 0xFF == ord(']'):
                    break
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Произошла ошибка: {e}")

        self.cap.release()
        cv2.destroyAllWindows()
