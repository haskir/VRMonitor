import threading
import time
from collections.abc import Callable
from typing import Literal

import cv2
import mediapipe as mp
import numpy as np
from loguru import logger
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from consts import TEST_CAMERA_TITLE


class CameraCaptureThread:
    """
    Отдельный поток для постоянного чтения веб-камеры.
    Решает проблему буферизации Windows и убирает задержку в 100-150мс.
    """

    def __init__(self, camera_index=0):
        # CAP_DSHOW ускоряет захват на Windows
        self.cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        self.cap.set(cv2.CAP_PROP_FPS, 60)
        self.ret, self.frame = self.cap.read()
        self.is_running: bool = True
        self.frame_id: int = 0
        self.thread: threading.Thread = threading.Thread(target=self._update, daemon=True)

    def start(self):
        self.thread.start()

    def _update(self):
        while self.is_running:
            # Постоянно вычитываем кадры, оставляя только самый свежий
            ret, frame = self.cap.read()
            if ret:
                self.ret = ret
                self.frame = frame
                self.frame_id += 1

    def read(self) -> tuple[bool, np.ndarray, int]:
        return self.ret, self.frame, self.frame_id

    def stop(self):
        self.is_running = False
        self.thread.join()
        self.cap.release()


class CameraController:
    def __init__(
        self,
        on_left_callback: Callable,
        on_right_callback: Callable,
        on_neutral_callback: Callable,
        on_up_callback: Callable,
        on_down_callback: Callable,
        angle_threshold: int,
        model_path: str = "static/face_landmarker.task",
    ):
        self.on_left: Callable = on_left_callback
        self.on_right: Callable = on_right_callback
        self.on_neutral: Callable = on_neutral_callback
        self.on_up: Callable = on_up_callback
        self.on_down: Callable = on_down_callback
        self.angle_threshold: int | float = angle_threshold
        self.camera_index: int = 0
        self.model_path: str = model_path
        self.is_on: bool = False

        self._angle_state: Literal[-1, 0, 1] = 0  # -1 влево, 1 вправо, 0 прямо
        self._y_state: Literal[0, 1, 2] = 0  # 1 встать, 2 сесть

        self._is_visible = False
        self._visualize_detection = True
        self._sit_mode: bool = True
        self.y_threshold = 0

        self.cam_thread = None

    def set_visible(self, is_visible: bool):
        self._is_visible = is_visible

    def set_visualize_detection(self, is_visible: bool):
        self._visualize_detection = is_visible

    def set_sit_mode(self, sit_mode: bool):
        self._sit_mode = sit_mode

    def on(self):
        if not self.is_on:
            self.is_on = True
            self._run()

    def off(self):
        self.is_on = False

    def set_y_threshold(self, threshold: int):
        logger.info(f"Установка порога Y: {threshold}")
        self.y_threshold = threshold if threshold > 0 else -threshold

    def set_camera_index(self, index: int):
        self.camera_index = index

    def _get_text_to_display(self, angle: float) -> str:
        if angle > 10:
            return f"Head tilt to the left ({angle:.2f}) [{self.angle_threshold}]"
        elif angle < -10:
            return f"Head tilt to the right ({angle:.2f}) [{self.angle_threshold}]"
        else:
            return f"Head is straight ({angle:.2f}) [{self.angle_threshold}]"

    @classmethod
    def _put_text_to_window(cls, text: str, frame, color: tuple[int, int, int] | None = None):
        cv2.putText(
            frame,
            text=text,
            org=(10, 30),
            fontFace=cv2.FONT_HERSHEY_SIMPLEX,
            fontScale=0.7,
            color=color if color else (255, 255, 255),
        )

    @classmethod
    def _calculate_head_tilt(cls, landmarks) -> float:
        left_eye = np.array([(landmarks[33][0], landmarks[33][1])])
        right_eye = np.array([(landmarks[263][0], landmarks[263][1])])

        dx = right_eye[0][0] - left_eye[0][0]
        dy = right_eye[0][1] - left_eye[0][1]
        angle: float = np.degrees(np.arctan2(dy, dx))
        return angle

    def _calculate_y(self, landmarks):
        if landmarks[0][1] > self.y_threshold:
            if self._y_state != 1:
                self.on_down()
            self._y_state = 1
        else:
            if self._y_state != 2:
                self.on_up()
            self._y_state = 2

    @classmethod
    def _visualize_face(cls, frame, landmarks):
        for x, y in landmarks:
            cv2.circle(
                frame,
                center=(int(x), int(y)),
                radius=1,
                color=(0, 255, 255),
                thickness=-1,
            )

    def _visualize_sit_y(self, frame):
        if self._sit_mode and self._visualize_detection:
            cv2.line(
                frame,
                (0, self.y_threshold),
                (frame.shape[1], self.y_threshold),
                (0, 0, 255),
                2,
            )

    def _run(self):
        logger.info(f"Запуск камеры {self.camera_index}")

        # Настройка нового API MediaPipe (Tasks API)
        base_options = python.BaseOptions(model_asset_path=self.model_path)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
            num_faces=1,
        )
        detector = vision.FaceLandmarker.create_from_options(options)

        # Запускаем фоновый поток чтения камеры
        self.cam_thread = CameraCaptureThread(self.camera_index)
        self.cam_thread.start()

        is_destroyed: bool = False
        is_created: bool = False
        last_processed_id: int = -1

        while self.is_on:
            # Быстро забираем свежий кадр из соседнего потока
            ret, frame, frame_id = self.cam_thread.read()

            if not ret or frame is None:
                time.sleep(0.001)  # Ждем, пока камера инициализируется
                continue
            if frame_id == last_processed_id:
                time.sleep(0.001)
                continue

            last_processed_id = frame_id  # Запоминаем, что взяли новый кадр в работу

            try:
                # Преобразуем изображение в RGB и в формат mp.Image (требование нового API)
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

                # Обнаружение лица
                detection_result = detector.detect(mp_image)

                # Новый API возвращает список лиц в face_landmarks
                if detection_result.face_landmarks:
                    # Берем первое найденное лицо
                    face_landmarks = detection_result.face_landmarks[0]

                    # Извлечение координат (структура данных изменилась, теперь это свойства объекта)
                    landmarks = [(lm.x * frame.shape[1], lm.y * frame.shape[0]) for lm in face_landmarks]

                    angle = self._calculate_head_tilt(landmarks)

                    if abs(angle) > self.angle_threshold:
                        if angle > 0:
                            if self._angle_state != -1:
                                self.on_left()
                            self._angle_state = -1
                        else:
                            if self._angle_state != 1:
                                self.on_right()
                            self._angle_state = 1
                    else:
                        self._angle_state = 0
                        self.on_neutral()

                    if self._sit_mode:
                        self._calculate_y(landmarks)

                    if self._is_visible and self._visualize_detection:
                        self._visualize_face(frame, landmarks)
                        self._visualize_sit_y(frame)
                        self._put_text_to_window(
                            self._get_text_to_display(angle),
                            frame,
                            (255, 0, 0),
                        )

                # Отрисовка
                if self._is_visible:
                    cv2.imshow(TEST_CAMERA_TITLE, frame)
                    is_created = True
                elif is_created and not is_destroyed:
                    cv2.destroyWindow(TEST_CAMERA_TITLE)
                    is_destroyed = True

                # Обработка выхода
                if cv2.waitKey(1) & 0xFF == ord("]"):
                    break

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Произошла ошибка: {e}")

        # Корректное завершение потоков и ресурсов
        if self.cam_thread:
            self.cam_thread.stop()
        detector.close()
        cv2.destroyAllWindows()
