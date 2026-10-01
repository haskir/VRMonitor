import threading
import time

from loguru import logger

from application.events import Event
from application.head_tracking import HeadTracking
from domain.camera import CameraMode

from .capture import CameraCaptureThread
from .face_tracker import MediaPipeFaceTracker
from .overlay import draw_face_mesh, draw_sit_lines, draw_status
from .preview import PreviewWindow
from .virtual_camera import VirtualCameraOutput

__all__ = ["CameraPipeline"]


class CameraPipeline:
    """
    Цикл обработки в отдельном потоке: кадр камеры -> поза головы -> HeadTracking,
    затем вывод картинки в окно предпросмотра и виртуальную камеру OBS
    """

    def __init__(self, tracking: HeadTracking):
        self._tracking = tracking
        self.virtual_cam_failed: Event[str] = Event()

        self._camera_index = 0
        self._camera_mode: CameraMode | None = None  # None - режим камеры по умолчанию
        self._preview_visible = False
        self._overlay = True
        self._virtual_cam = False
        self._virtual_cam_mesh = True

        self._is_on = False
        self._worker: threading.Thread | None = None

    # --- Настройки (из потока UI; поток камеры читает их на каждом кадре) ---

    def set_camera(self, index: int):
        self._camera_index = index

    def set_mode(self, mode: CameraMode | None):
        logger.info(f"Режим камеры: {mode if mode else 'по умолчанию'}")
        self._camera_mode = mode

    def set_preview_visible(self, visible: bool):
        self._preview_visible = visible

    def set_overlay(self, enabled: bool):
        self._overlay = enabled

    def set_virtual_cam(self, enabled: bool):
        logger.info(f"Вывод в виртуальную камеру OBS: {'вкл' if enabled else 'выкл'}")
        self._virtual_cam = enabled

    def set_virtual_cam_mesh(self, enabled: bool):
        self._virtual_cam_mesh = enabled

    # --- Запуск и остановка ---

    def start(self):
        if self._is_on:
            return
        # Предыдущий цикл мог ещё не завершиться
        if self._worker and self._worker.is_alive():
            self._worker.join()
        self._is_on = True
        self._worker = threading.Thread(target=self._safe_run, daemon=True)
        self._worker.start()

    def stop(self, wait: bool = False):
        self._is_on = False
        if wait and self._worker and self._worker is not threading.current_thread():
            self._worker.join(timeout=5)

    def _safe_run(self):
        try:
            self._run()
        except Exception as e:
            logger.exception(f"Ошибка в цикле обработки камеры: {e}")
        finally:
            self._is_on = False

    def _virtual_cam_error(self, message: str):
        # Выключаем вывод, чтобы не пытаться переоткрыть камеру на каждом кадре
        self._virtual_cam = False
        self.virtual_cam_failed.emit(message)

    def _run(self):
        logger.info(f"Запуск камеры {self._camera_index}")
        face_tracker = MediaPipeFaceTracker()
        active_capture = (self._camera_index, self._camera_mode)
        capture = CameraCaptureThread(*active_capture)
        capture.start()
        preview = PreviewWindow()
        virtual_cam = VirtualCameraOutput(on_error=self._virtual_cam_error)

        fps = 0.0
        last_frame_time = time.monotonic()
        last_processed_id = -1
        start_time = time.monotonic()

        try:
            while self._is_on:
                # Камеру или её режим поменяли на ходу - переоткрываем захват
                if (self._camera_index, self._camera_mode) != active_capture:
                    capture.stop()
                    active_capture = (self._camera_index, self._camera_mode)
                    capture = CameraCaptureThread(*active_capture)
                    capture.start()
                    last_processed_id = -1

                # Ждём свежий кадр из потока захвата
                ret, frame, frame_id = capture.wait_for_frame(last_processed_id)
                if not ret or frame is None or frame_id == last_processed_id:
                    continue
                last_processed_id = frame_id
                now = time.monotonic()
                fps = 0.9 * fps + 0.1 / max(now - last_frame_time, 1e-3)  # Сглаженный fps обработки
                last_frame_time = now

                try:
                    face = face_tracker.detect(frame, int((now - start_time) * 1000))
                    if face:
                        self._tracking.on_pose(face.pose)

                    # Рисование - уже после нажатий клавиш, чтобы не добавлять им задержку
                    show_overlay = self._preview_visible and self._overlay
                    send_virtual_cam = self._virtual_cam
                    mesh_frame = frame
                    if face and (show_overlay or (send_virtual_cam and self._virtual_cam_mesh)):
                        mesh_frame = frame.copy()
                        draw_face_mesh(mesh_frame, face.landmarks)

                    if send_virtual_cam:
                        virtual_cam.send(mesh_frame if self._virtual_cam_mesh else frame, capture.fps)
                    elif virtual_cam.is_open:
                        virtual_cam.close()

                    # send() копирует кадр синхронно, так что дорисовывать предпросмотр поверх уже безопасно
                    if self._preview_visible:
                        if show_overlay:
                            overlay = self._tracking.overlay()
                            draw_sit_lines(mesh_frame, overlay)
                            draw_status(mesh_frame, face.pose.tilt if face else 0.0, overlay, fps)
                        preview.show(mesh_frame)
                    else:
                        preview.hide()
                except Exception as e:
                    logger.error(f"Ошибка обработки кадра: {e}")
        finally:
            capture.stop()
            virtual_cam.close()
            face_tracker.close()
            preview.close()
