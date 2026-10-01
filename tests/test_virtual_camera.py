import sys
import types

import numpy as np
import pytest

from infrastructure.camera.virtual_camera import VirtualCameraOutput


class FakeCamera:
    """Заглушка pyvirtualcam.Camera: запоминает параметры и отправленные кадры"""

    instances: list["FakeCamera"] = []
    fail_on_open: Exception | None = None
    fail_on_send: Exception | None = None

    def __init__(self, width, height, fps, fmt=None, backend=None):
        if FakeCamera.fail_on_open:
            raise FakeCamera.fail_on_open
        self.args = (width, height, fps)
        self.fmt = fmt
        self.backend = backend
        self.device = "OBS Virtual Camera"
        self.frames: list[np.ndarray] = []
        self.closed = False
        FakeCamera.instances.append(self)

    def send(self, frame):
        if FakeCamera.fail_on_send:
            raise FakeCamera.fail_on_send
        self.frames.append(frame)

    def close(self):
        self.closed = True


@pytest.fixture
def fake_pyvirtualcam(monkeypatch):
    FakeCamera.instances = []
    FakeCamera.fail_on_open = None
    FakeCamera.fail_on_send = None
    module = types.ModuleType("pyvirtualcam")
    module.Camera = FakeCamera
    module.PixelFormat = types.SimpleNamespace(BGR="BGR")
    monkeypatch.setitem(sys.modules, "pyvirtualcam", module)
    return FakeCamera


def frame(width=640, height=480, value=0) -> np.ndarray:
    return np.full((height, width, 3), value, np.uint8)


def test_opens_lazily_with_frame_format(fake_pyvirtualcam):
    output = VirtualCameraOutput()
    assert not output.is_open
    assert fake_pyvirtualcam.instances == []

    assert output.send(frame(1280, 720), fps=59.94)
    assert output.is_open
    [camera] = fake_pyvirtualcam.instances
    assert camera.args == (1280, 720, 60)
    assert camera.fmt == "BGR" and camera.backend == "obs"
    assert len(camera.frames) == 1


def test_reuses_camera_for_same_format(fake_pyvirtualcam):
    output = VirtualCameraOutput()
    for _ in range(5):
        output.send(frame(), fps=30)
    assert len(fake_pyvirtualcam.instances) == 1
    assert len(fake_pyvirtualcam.instances[0].frames) == 5


@pytest.mark.parametrize(
    ("second_frame", "second_fps"),
    [(frame(1920, 1080), 30), (frame(), 60)],
    ids=["size", "fps"],
)
def test_reopens_on_format_change(fake_pyvirtualcam, second_frame, second_fps):
    output = VirtualCameraOutput()
    output.send(frame(), fps=30)
    output.send(second_frame, fps=second_fps)
    first, second = fake_pyvirtualcam.instances
    assert first.closed and not second.closed
    assert second.args == (second_frame.shape[1], second_frame.shape[0], second_fps)


def test_fps_is_at_least_one(fake_pyvirtualcam):
    VirtualCameraOutput().send(frame(), fps=0.2)
    assert fake_pyvirtualcam.instances[0].args[2] == 1


def test_open_error_is_reported_and_retried(fake_pyvirtualcam):
    """OBS не установлен или его собственная виртуальная камера уже запущена"""
    errors = []
    output = VirtualCameraOutput(on_error=errors.append)
    fake_pyvirtualcam.fail_on_open = RuntimeError("virtual camera output could not be started")

    assert not output.send(frame(), fps=30)
    assert not output.is_open
    assert len(errors) == 1
    assert "виртуальную камеру OBS" in errors[0] and "could not be started" in errors[0]

    fake_pyvirtualcam.fail_on_open = None
    assert output.send(frame(), fps=30)
    assert output.is_open


def test_send_error_closes_camera(fake_pyvirtualcam):
    errors = []
    output = VirtualCameraOutput(on_error=errors.append)
    output.send(frame(), fps=30)
    fake_pyvirtualcam.fail_on_send = RuntimeError("boom")

    assert not output.send(frame(), fps=30)
    assert not output.is_open
    assert fake_pyvirtualcam.instances[0].closed
    assert len(errors) == 1


def test_error_without_callback_does_not_raise(fake_pyvirtualcam):
    fake_pyvirtualcam.fail_on_open = RuntimeError("no OBS")
    assert not VirtualCameraOutput().send(frame(), fps=30)


def test_close_is_idempotent(fake_pyvirtualcam):
    output = VirtualCameraOutput()
    output.close()  # Ещё не открыта
    output.send(frame(), fps=30)
    output.close()
    output.close()
    assert not output.is_open
    assert fake_pyvirtualcam.instances[0].closed
