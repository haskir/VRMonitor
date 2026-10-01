"""Вывод в OBS внутри цикла камеры - с заглушками вместо камеры, MediaPipe и pyvirtualcam"""

import threading
import time
import types

import numpy as np
import pytest

from application.game_keys import GameKeys
from application.head_tracking import HeadTracking
from application.input_controller import InputController
from domain.pose import HeadPose
from infrastructure.camera.blank_frames import BlankFrameDetector
from infrastructure.camera.face_tracker import FaceDetection
from infrastructure.camera.pipeline import CameraPipeline
from tests.fakes import FakeClock, FakeGameWindow, RecordingKeySender, ToggleCrouchGame

WIDTH, HEIGHT, FPS = 320, 240, 30.0
RAW_VALUE = 60  # Серый кадр: сетка лица рисуется жёлтым, её легко отличить


class FakeCapture:
    value = RAW_VALUE  # Яркость кадров; 0 - камера занята и отдаёт чёрное

    def __init__(self, index, mode):
        self.fps = FPS
        self._frame_id = 0
        self.stopped = False

    def start(self):
        pass

    def wait_for_frame(self, last_frame_id, timeout=0.5):
        time.sleep(0.005)
        self._frame_id += 1
        return True, np.full((HEIGHT, WIDTH, 3), FakeCapture.value, np.uint8), self._frame_id

    def stop(self):
        self.stopped = True


class FakeFaceTracker:
    def detect(self, frame, timestamp_ms):
        # 478 точек сеткой 20x24 в центре кадра - столько возвращает MediaPipe Face Landmarker
        landmarks = [types.SimpleNamespace(x=0.3 + 0.02 * (i % 20), y=0.3 + 0.4 * (i // 20) / 24) for i in range(478)]
        return FaceDetection(pose=HeadPose(tilt=0.0, y=100.0), landmarks=landmarks)

    def close(self):
        pass


class FakePreview:
    def show(self, frame):
        pass

    def hide(self):
        pass

    def close(self):
        pass


class RecordingVirtualCam:
    """Заглушка VirtualCameraOutput; fail=True - имитирует ошибку OBS при первой отправке"""

    instances: list["RecordingVirtualCam"] = []
    fail = False

    def __init__(self, on_error=None):
        self._on_error = on_error
        self.frames: list[tuple[np.ndarray, float]] = []
        self.is_open = False
        self.close_count = 0
        self._lock = threading.Lock()
        RecordingVirtualCam.instances.append(self)

    def send(self, frame, fps):
        if RecordingVirtualCam.fail:
            if self._on_error:
                self._on_error("Не удалось вывести изображение в виртуальную камеру OBS: занята")
            return False
        with self._lock:
            self.is_open = True
            self.frames.append((frame.copy(), fps))
        return True

    def close(self):
        self.is_open = False
        self.close_count += 1


def wait_until(condition, timeout=3.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if condition():
            return True
        time.sleep(0.01)
    return False


@pytest.fixture
def pipeline():
    RecordingVirtualCam.instances = []
    RecordingVirtualCam.fail = False
    FakeCapture.value = RAW_VALUE
    clock = FakeClock()
    game = ToggleCrouchGame(clock)
    tracking = HeadTracking(InputController(GameKeys(RecordingKeySender()), FakeGameWindow(), game, clock=clock))
    pipeline = CameraPipeline(
        tracking,
        capture_factory=FakeCapture,
        face_tracker_factory=FakeFaceTracker,
        virtual_cam_factory=RecordingVirtualCam,
        preview_factory=FakePreview,
    )
    yield pipeline
    pipeline.stop(wait=True)


def vcam() -> RecordingVirtualCam:
    assert wait_until(lambda: RecordingVirtualCam.instances)
    return RecordingVirtualCam.instances[0]


def test_nothing_sent_when_disabled(pipeline):
    pipeline.start()
    time.sleep(0.2)
    assert vcam().frames == []


def test_frames_sent_with_capture_fps(pipeline):
    pipeline.set_virtual_cam(True)
    pipeline.set_virtual_cam_mesh(False)
    pipeline.start()
    output = vcam()
    assert wait_until(lambda: len(output.frames) >= 5)
    frame, fps = output.frames[-1]
    assert frame.shape == (HEIGHT, WIDTH, 3)
    assert fps == FPS
    assert (frame == RAW_VALUE).all()  # Без сетки - исходный кадр без изменений


def test_mesh_drawn_only_for_obs_when_enabled(pipeline):
    pipeline.set_virtual_cam(True)
    pipeline.set_virtual_cam_mesh(True)
    pipeline.set_overlay(False)
    pipeline.start()
    output = vcam()
    assert wait_until(lambda: len(output.frames) >= 3)
    frame, _ = output.frames[-1]
    assert not (frame == RAW_VALUE).all()  # Сетка лица нарисована
    assert (frame == RAW_VALUE).mean() > 0.5  # но не залила весь кадр


def test_toggling_off_closes_output(pipeline):
    pipeline.set_virtual_cam(True)
    pipeline.start()
    output = vcam()
    assert wait_until(lambda: output.is_open)
    pipeline.set_virtual_cam(False)
    assert wait_until(lambda: not output.is_open)
    sent = len(output.frames)
    time.sleep(0.1)
    assert len(output.frames) == sent


def test_failure_is_reported_once_and_output_disabled(pipeline):
    RecordingVirtualCam.fail = True
    errors = []
    pipeline.virtual_cam_failed.connect(errors.append)
    pipeline.set_virtual_cam(True)
    pipeline.start()
    assert wait_until(lambda: errors)
    time.sleep(0.2)
    assert len(errors) == 1  # Не пытаемся переоткрыть на каждом кадре
    assert "OBS" in errors[0]


def test_stop_closes_output(pipeline):
    pipeline.set_virtual_cam(True)
    pipeline.start()
    output = vcam()
    assert wait_until(lambda: output.is_open)
    pipeline.stop(wait=True)
    assert not output.is_open


def test_black_frames_are_reported(pipeline):
    pipeline._blank_frames = BlankFrameDetector(blank_seconds=0.1)
    FakeCapture.value = 0  # Камеру держит другая программа
    pipeline.start()
    assert wait_until(lambda: pipeline.is_blank)

    FakeCapture.value = RAW_VALUE  # Камеру освободили
    assert wait_until(lambda: not pipeline.is_blank)

    FakeCapture.value = 0
    assert wait_until(lambda: pipeline.is_blank)
    pipeline.stop(wait=True)
    assert not pipeline.is_blank  # После остановки предупреждение не висит
