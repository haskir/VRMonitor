import pytest

from application.app import App
from application.game_keys import GameKeys
from application.head_tracking import HeadTracking
from application.input_controller import InputController
from domain.pose import HeadPose
from domain.settings import AppSettings
from tests.fakes import (
    FakeCameraCatalog,
    FakeClock,
    FakeGameWindow,
    MemorySettingsRepository,
    RecordingCameraRuntime,
    RecordingKeySender,
    ToggleCrouchGame,
)


def make_app(settings: AppSettings | None = None):
    clock = FakeClock()
    sender = RecordingKeySender()
    input_controller = InputController(GameKeys(sender), FakeGameWindow(), ToggleCrouchGame(clock), clock=clock)
    tracking = HeadTracking(input_controller, clock=clock)
    camera = RecordingCameraRuntime()
    repository = MemorySettingsRepository(settings)
    app = App(repository, FakeCameraCatalog(), camera, tracking, input_controller)  # type: ignore
    return app, camera, repository, sender, tracking


def test_settings_applied_on_start():
    app, camera, *_ = make_app(AppSettings(visualize=True, camera_index=3))
    assert ("set_overlay", True) in camera.calls
    assert ("set_camera", 3) in camera.calls


def test_update_applies_and_saves_once():
    app, camera, repository, *_ = make_app()
    changes = []
    app.settings_changed.connect(changes.append)

    app.update(virtual_cam=True)
    app.update(virtual_cam=True)  # Без изменений - ничего не делаем
    assert camera.calls.count(("set_virtual_cam", True)) == 1
    assert len(changes) == 1

    app.save()
    app.save()
    assert len(repository.saved) == 1


def test_unknown_setting_is_rejected():
    app, *_ = make_app()
    with pytest.raises(AttributeError):
        app.update(no_such_setting=1)


def test_angle_threshold_reaches_tracking():
    app, _, _, sender, tracking = make_app()
    app.update(angle_threshold=40)
    tracking.on_pose(HeadPose(tilt=30, y=100))
    assert sender.events == []
    tracking.on_pose(HeadPose(tilt=45, y=100))
    assert sender.events == [("down", "Q")]


def test_running_and_shutdown():
    app, camera, repository, *_ = make_app()
    app.set_running(True)
    assert camera.running
    app.update(sit_y=150)
    app.shutdown()
    assert not camera.running
    assert repository.saved[-1].sit_y == 150
