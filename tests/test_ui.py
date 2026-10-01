import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from application.app import App  # noqa: E402
from application.game_keys import GameKeys  # noqa: E402
from application.head_tracking import HeadTracking  # noqa: E402
from application.input_controller import InputController  # noqa: E402
from domain.bindings import GameBindings, KeyBinding, KeyMode  # noqa: E402
from domain.settings import AppSettings  # noqa: E402
from tests.fakes import (  # noqa: E402
    FakeCameraCatalog,
    FakeClock,
    FakeGameWindow,
    MemorySettingsRepository,
    RecordingCameraRuntime,
    RecordingKeySender,
    ToggleCrouchGame,
)
from ui.widgets.key_capture import KeyCaptureButton, key_title  # noqa: E402
from ui.widgets.threshold_gauge import ThresholdGauge  # noqa: E402


@pytest.fixture(scope="module")
def qt():
    return QApplication.instance() or QApplication([])


def test_key_capture(qt):
    button = KeyCaptureButton("q")
    captured = []
    button.key_changed.connect(captured.append)
    button.show()

    button.click()
    assert button.text() == "Жду клавишу…"
    QTest.keyClick(button, Qt.Key.Key_Z)
    assert captured == ["z"] and button.text() == "Z" and not button.isChecked()

    button.click()
    QTest.keyClick(button, Qt.Key.Key_Control)
    assert captured[-1] == "ctrl" and button.text() == "Ctrl"

    button.click()
    QTest.keyClick(button, Qt.Key.Key_Escape)
    assert button.button == "ctrl" and len(captured) == 2  # Esc - отмена


def test_key_titles():
    assert key_title("Q") == "Q"
    assert key_title("space") == "Пробел"
    assert key_title("f5") == "F5"


def test_gauge(qt):
    gauge = ThresholdGauge(1, 60, 20)
    values = []
    gauge.value_changed.connect(values.append)
    gauge.set_value(100)
    assert gauge.value == 60
    gauge.set_value(20, emit=False)
    QTest.keyClick(gauge, Qt.Key.Key_Right)
    assert values == [60, 21]

    gauge.set_live(25)
    assert gauge.is_live_active
    gauge.set_live(None)
    assert not gauge.is_live_active


def make_window(settings: AppSettings | None = None):
    from ui.main_window import MainWindow

    clock = FakeClock()
    input_controller = InputController(
        GameKeys(RecordingKeySender()), FakeGameWindow(), ToggleCrouchGame(clock), clock=clock
    )
    tracking = HeadTracking(input_controller, clock=clock)
    camera = RecordingCameraRuntime()
    app = App(MemorySettingsRepository(settings), FakeCameraCatalog(), camera, tracking, input_controller)
    return MainWindow(app), app, camera


def test_main_window_controls_settings(qt):
    window, app, camera = make_window(AppSettings(sit_y=200))
    assert app.settings.camera_index == 1  # Единственная доступная камера выбрана и применена

    window.run_button.click()
    assert camera.running and app.is_running
    assert window.run_button.text() == "Выключить распознавание"

    window.sit_gauge.set_value(250)
    assert app.settings.sit_y == 250
    window.angle_gauge.set_value(30)
    assert app.settings.angle_threshold == 30

    window.left_row.key_button.click()
    QTest.keyClick(window.left_row.key_button, Qt.Key.Key_A)
    assert app.settings.bindings.left == KeyBinding("a", KeyMode.HOLD)
    window.sit_row.mode_box.setCurrentIndex(window.sit_row.mode_box.findData(KeyMode.HOLD))
    assert app.settings.bindings.sit.mode == KeyMode.HOLD

    window._reset_bindings()
    assert app.settings.bindings == GameBindings.default()
    assert window.left_row.key_button.text() == "Q"

    window._on_calibrated(270)
    assert app.settings.sit_y == 270 and window.sit_gauge.value == 270

    window.close()
    assert not camera.running


def test_blank_frame_warning(qt):
    window, app, camera = make_window()
    window.show()
    camera.is_blank = True
    window._refresh_live()
    assert window.blank_warning.isHidden()  # Распознавание выключено - камера не работает

    window.run_button.click()
    window._refresh_live()
    assert not window.blank_warning.isHidden()
    assert "OBS Virtual Camera" in window.blank_warning.text()
    assert window.face_chip.text() == "Чёрный кадр с камеры"

    camera.is_blank = False
    window._refresh_live()
    assert window.blank_warning.isHidden()
    window.close()
