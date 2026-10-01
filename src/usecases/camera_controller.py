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
from mediapipe.tasks.python.vision import FaceLandmarksConnections

from consts import (
    CALIBRATION_SECONDS,
    CALIBRATION_TOLERANCE,
    CAMERA_PREVIEW_WIDTH,
    DEFAULT_SIT_DEPTH,
    TEST_CAMERA_TITLE,
    Y_SCALE,
)
from models import CameraMode
from usecases.model_provider import ensure_face_landmarker
from usecases.virtual_camera import VirtualCameraOutput

# Пары индексов точек, образующие рёбра сетки лица
FACE_MESH_EDGES = np.array([(c.start, c.end) for c in FaceLandmarksConnections.FACE_LANDMARKS_TESSELATION])


class CameraCaptureThread:
    """
    Отдельный поток для постоянного чтения веб-камеры.
    Решает проблему буферизации Windows и убирает задержку в 100-150мс.
    """

    def __init__(self, camera_index: int = 0, mode: CameraMode | None = None):
        # CAP_DSHOW ускоряет захват на Windows
        self.cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
        if mode:
            # Порядок важен: DirectShow применяет FOURCC только после размера и fps,
            # иначе молча остаётся на YUY2 (1080p в нём - 5 fps вместо 60)
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, mode.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, mode.height)
            self.cap.set(cv2.CAP_PROP_FPS, mode.fps)
            if len(mode.fourcc) == 4:  # RGB24 и подобные задаются не FOURCC, а форматом по умолчанию
                self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc(*mode.fourcc))
        fourcc = int(self.cap.get(cv2.CAP_PROP_FOURCC)).to_bytes(4, "little").decode("ascii", "replace")
        logger.info(
            f"Камера {camera_index}: {int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x"
            f"{int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))} @ {self.cap.get(cv2.CAP_PROP_FPS):.0f} fps ({fourcc})"
        )
        self.fps: float = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
        self.ret, self.frame = self.cap.read()
        self.is_running: bool = True
        self.frame_id: int = 0
        self._new_frame = threading.Condition()
        self.thread: threading.Thread = threading.Thread(target=self._update, daemon=True)

    def start(self):
        self.thread.start()

    def _update(self):
        while self.is_running:
            # Постоянно вычитываем кадры, оставляя только самый свежий
            ret, frame = self.cap.read()
            if ret:
                with self._new_frame:
                    self.ret = ret
                    self.frame = frame
                    self.frame_id += 1
                    self._new_frame.notify_all()

    def read(self) -> tuple[bool, np.ndarray, int]:
        with self._new_frame:
            return self.ret, self.frame, self.frame_id

    def wait_for_frame(self, last_frame_id: int, timeout: float = 0.5) -> tuple[bool, np.ndarray, int]:
        """Блокируется до появления кадра новее last_frame_id (без холостого опроса)"""
        with self._new_frame:
            self._new_frame.wait_for(lambda: self.frame_id != last_frame_id or not self.is_running, timeout)
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
        on_calibrated_callback: Callable[[int], None] | None = None,
        on_virtual_cam_error_callback: Callable[[str], None] | None = None,
    ):
        self.on_left: Callable = on_left_callback
        self.on_right: Callable = on_right_callback
        self.on_neutral: Callable = on_neutral_callback
        self.on_up: Callable = on_up_callback
        self.on_down: Callable = on_down_callback
        self.on_calibrated: Callable[[int], None] | None = on_calibrated_callback
        self.angle_threshold: int | float = angle_threshold
        self.camera_index: int = 0
        self.camera_mode: CameraMode | None = None  # None - режим камеры по умолчанию
        self.is_on: bool = False

        self._angle_state: Literal[-1, 0, 1] = 0  # -1 влево, 1 вправо, 0 прямо
        self._y_state: Literal[0, 1, 2] = 0  # 1 встать, 2 сесть

        self._is_visible = False
        self._visualize_detection = True
        self._sit_mode: bool = True
        self.y_threshold = 0  # 0 - порог не задан, приседания не отслеживаются

        # Авто-калибровка: база - верхнее положение головы, порог = база + глубина приседа
        self._auto_calibrate: bool = False
        self._base_y: int | None = None
        self._sit_depth: int = DEFAULT_SIT_DEPTH
        self._anchor_y: float | None = None
        self._anchor_time: float = 0.0

        # Вывод картинки в виртуальную камеру OBS
        self._virtual_cam: bool = False
        self._virtual_cam_mesh: bool = True
        self._on_virtual_cam_error = on_virtual_cam_error_callback

        self.cam_thread = None
        self._worker: threading.Thread | None = None

    def set_visible(self, is_visible: bool):
        self._is_visible = is_visible

    def set_visualize_detection(self, is_visible: bool):
        self._visualize_detection = is_visible

    def set_sit_mode(self, sit_mode: bool):
        self._sit_mode = sit_mode

    def set_virtual_cam(self, enabled: bool):
        logger.info(f"Вывод в виртуальную камеру OBS: {'вкл' if enabled else 'выкл'}")
        self._virtual_cam = enabled

    def set_virtual_cam_mesh(self, enabled: bool):
        self._virtual_cam_mesh = enabled

    def _virtual_cam_failed(self, message: str):
        # Выключаем вывод, чтобы не пытаться переоткрыть камеру на каждом кадре
        self._virtual_cam = False
        if self._on_virtual_cam_error:
            self._on_virtual_cam_error(message)

    def on(self):
        if self.is_on:
            return
        # Предыдущий цикл мог ещё не завершиться
        if self._worker and self._worker.is_alive():
            self._worker.join()
        self.is_on = True
        # Цикл обработки крутится в отдельном потоке, чтобы не блокировать GUI
        self._worker = threading.Thread(target=self._safe_run, daemon=True)
        self._worker.start()

    def off(self, wait: bool = False):
        self.is_on = False
        if wait and self._worker and self._worker is not threading.current_thread():
            self._worker.join(timeout=5)

    def _safe_run(self):
        try:
            self._run()
        except Exception as e:
            logger.exception(f"Ошибка в цикле обработки камеры: {e}")
        finally:
            self.is_on = False

    def set_y_threshold(self, threshold: int):
        threshold = abs(threshold)
        if threshold == self.y_threshold:
            return
        logger.info(f"Установка порога Y: {threshold}")
        self.y_threshold = threshold
        # Ручная правка порога при известной базе задаёт глубину приседа
        if self._base_y is not None and threshold > self._base_y:
            self._sit_depth = threshold - self._base_y

    def set_auto_calibrate(self, enabled: bool):
        logger.info(f"Авто-калибровка: {'вкл' if enabled else 'выкл'}")
        self._auto_calibrate = enabled
        self._anchor_y = None

    def _update_calibration(self, head_y: float):
        """Если голова долго неподвижна в верхнем положении - запоминаем её Y как базу"""
        if not self._auto_calibrate:
            return
        # Калибруемся только стоя, иначе долгое сидение станет новым "верхом"
        if self.y_threshold and head_y > self.y_threshold:
            self._anchor_y = None
            return

        now = time.monotonic()
        if self._anchor_y is None or abs(head_y - self._anchor_y) > CALIBRATION_TOLERANCE:
            self._anchor_y = head_y
            self._anchor_time = now
            return
        if now - self._anchor_time < CALIBRATION_SECONDS:
            return

        self._anchor_time = now
        base_y = int(self._anchor_y)
        if self._base_y is None and self.y_threshold > base_y:
            # Первая калибровка: сохраняем глубину, которую пользователь выставил вручную
            self._sit_depth = self.y_threshold - base_y
        self._base_y = base_y
        new_threshold = base_y + self._sit_depth
        if new_threshold == self.y_threshold:
            return
        logger.info(f"Авто-калибровка: верх Y={base_y}, порог приседа Y={new_threshold}")
        self.y_threshold = new_threshold
        if self.on_calibrated:
            self.on_calibrated(new_threshold)

    def set_camera_index(self, index: int):
        self.camera_index = index

    def set_camera_mode(self, mode: CameraMode | None):
        logger.info(f"Режим камеры: {mode if mode else 'по умолчанию'}")
        self.camera_mode = mode

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
    def _calculate_head_tilt(cls, face_landmarks, width: int, height: int) -> float:
        # Внешние уголки глаз; координаты нормированы, поэтому учитываем пропорции кадра
        left_eye, right_eye = face_landmarks[33], face_landmarks[263]
        dx = (right_eye.x - left_eye.x) * width
        dy = (right_eye.y - left_eye.y) * height
        return float(np.degrees(np.arctan2(dy, dx)))

    def _calculate_y(self, head_y: float):
        self._update_calibration(head_y)
        if not self.y_threshold:
            return
        if head_y > self.y_threshold:
            if self._y_state != 1:
                self.on_down()
            self._y_state = 1
        else:
            if self._y_state != 2:
                self.on_up()
            self._y_state = 2

    @classmethod
    def _draw_face_mesh(cls, frame, face_landmarks):
        height, width = frame.shape[:2]
        points = np.array([(lm.x * width, lm.y * height) for lm in face_landmarks], dtype=np.int32)
        # Все рёбра сетки одним вызовом - на порядок быстрее, чем рисовать их по одному
        cv2.polylines(frame, list(points[FACE_MESH_EDGES]), False, (0, 255, 255), 1, cv2.LINE_AA)

    def _visualize_sit_y(self, frame):
        if not (self._sit_mode and self._visualize_detection):
            return
        height, width = frame.shape[:2]
        if self._base_y is not None:
            base_px = int(self._base_y * height / Y_SCALE)
            cv2.line(frame, (0, base_px), (width, base_px), (0, 255, 0), 1)
        threshold_px = int(self.y_threshold * height / Y_SCALE)
        cv2.line(frame, (0, threshold_px), (width, threshold_px), (0, 0, 255), 2)

    def _run(self):
        logger.info(f"Запуск камеры {self.camera_index}")

        # Настройка нового API MediaPipe (Tasks API)
        model_path = ensure_face_landmarker()
        base_options = python.BaseOptions(model_asset_path=str(model_path))
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
            num_faces=1,
            # VIDEO-режим отслеживает лицо между кадрами вместо поиска с нуля - быстрее и стабильнее
            running_mode=vision.RunningMode.VIDEO,
        )
        detector = vision.FaceLandmarker.create_from_options(options)

        # Запускаем фоновый поток чтения камеры
        active_capture = (self.camera_index, self.camera_mode)
        self.cam_thread = CameraCaptureThread(*active_capture)
        self.cam_thread.start()
        fps: float = 0.0
        last_frame_time = time.monotonic()

        is_window_shown: bool = False
        virtual_cam = VirtualCameraOutput(on_error=self._virtual_cam_failed)
        last_processed_id: int = -1
        start_time = time.monotonic()
        last_timestamp_ms: int = -1

        while self.is_on:
            # Камеру или её режим поменяли на ходу - переоткрываем захват
            if (self.camera_index, self.camera_mode) != active_capture:
                self.cam_thread.stop()
                active_capture = (self.camera_index, self.camera_mode)
                self.cam_thread = CameraCaptureThread(*active_capture)
                self.cam_thread.start()
                last_processed_id = -1

            # Ждём свежий кадр из соседнего потока
            ret, frame, frame_id = self.cam_thread.wait_for_frame(last_processed_id)

            if not ret or frame is None or frame_id == last_processed_id:
                continue

            last_processed_id = frame_id  # Запоминаем, что взяли новый кадр в работу
            now = time.monotonic()
            fps = 0.9 * fps + 0.1 / max(now - last_frame_time, 1e-3)  # Сглаженный fps обработки
            last_frame_time = now

            try:
                # Преобразуем изображение в RGB и в формат mp.Image (требование нового API)
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

                # Обнаружение лица
                # VIDEO-режим требует строго возрастающих меток времени
                timestamp_ms = max(int((time.monotonic() - start_time) * 1000), last_timestamp_ms + 1)
                last_timestamp_ms = timestamp_ms
                detection_result = detector.detect_for_video(mp_image, timestamp_ms)

                face_landmarks = None
                angle = 0.0
                # Новый API возвращает список лиц в face_landmarks
                if detection_result.face_landmarks:
                    # Берем первое найденное лицо
                    face_landmarks = detection_result.face_landmarks[0]
                    angle = self._calculate_head_tilt(face_landmarks, frame.shape[1], frame.shape[0])

                    if abs(angle) > self.angle_threshold:
                        if angle > 0:
                            if self._angle_state != -1:
                                self.on_left()
                            self._angle_state = -1
                        else:
                            if self._angle_state != 1:
                                self.on_right()
                            self._angle_state = 1
                    elif self._angle_state != 0:
                        self._angle_state = 0
                        self.on_neutral()

                    if self._sit_mode:
                        self._calculate_y(face_landmarks[0].y * Y_SCALE)

                # Рисование - уже после нажатий клавиш, чтобы не добавлять им задержку
                show_preview_overlay = self._is_visible and self._visualize_detection
                send_virtual_cam = self._virtual_cam
                mesh_frame = frame
                if face_landmarks and (show_preview_overlay or (send_virtual_cam and self._virtual_cam_mesh)):
                    mesh_frame = frame.copy()
                    self._draw_face_mesh(mesh_frame, face_landmarks)

                if send_virtual_cam:
                    virtual_cam.send(mesh_frame if self._virtual_cam_mesh else frame, self.cam_thread.fps)
                elif virtual_cam.is_open:
                    virtual_cam.close()

                # send() копирует кадр синхронно, так что дорисовывать предпросмотр поверх уже безопасно
                preview_frame = mesh_frame
                if show_preview_overlay:
                    self._visualize_sit_y(preview_frame)
                    self._put_text_to_window(
                        f"{self._get_text_to_display(angle)} {fps:.0f} fps",
                        preview_frame,
                        (255, 0, 0),
                    )

                # Отрисовка
                if self._is_visible:
                    if not is_window_shown:
                        # Окно масштабируемое, иначе кадр 1080p/1440p не влезет в экран
                        cv2.namedWindow(TEST_CAMERA_TITLE, cv2.WINDOW_NORMAL)
                        height, width = frame.shape[:2]
                        preview_width = min(width, CAMERA_PREVIEW_WIDTH)
                        cv2.resizeWindow(TEST_CAMERA_TITLE, preview_width, height * preview_width // width)
                    cv2.imshow(TEST_CAMERA_TITLE, preview_frame)
                    is_window_shown = True
                elif is_window_shown:
                    cv2.destroyWindow(TEST_CAMERA_TITLE)
                    is_window_shown = False

                # waitKey стоит ~2 мс, поэтому крутим цикл событий окна только когда оно показано
                if is_window_shown and cv2.waitKey(1) & 0xFF == ord("]"):
                    break

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Произошла ошибка: {e}")

        # Корректное завершение потоков и ресурсов
        if self.cam_thread:
            self.cam_thread.stop()
        virtual_cam.close()
        detector.close()
        cv2.destroyAllWindows()
