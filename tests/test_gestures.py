from domain.gestures import LeanDetector, SitDetector
from domain.pose import Lean


def test_lean_reports_only_changes():
    detector = LeanDetector(threshold=20)
    assert detector.update(5) is None  # Прямо - и так нейтраль
    assert detector.update(25) == Lean.LEFT
    assert detector.update(30) is None
    assert detector.update(-25) == Lean.RIGHT
    assert detector.update(10) == Lean.NONE


def test_sit_without_threshold_is_ignored():
    detector = SitDetector(threshold=0)
    assert detector.update(400, now=0).sitting is None


def test_sit_reports_first_state_and_changes():
    detector = SitDetector(threshold=200)
    assert detector.update(150, now=0).sitting is False
    assert detector.update(160, now=0).sitting is None
    assert detector.update(250, now=0).sitting is True
    assert detector.update(150, now=0).sitting is False


def test_auto_calibration_keeps_manual_depth():
    detector = SitDetector(threshold=230, auto_calibrate=True, calibration_seconds=20)
    detector.update(150, now=0)
    assert detector.update(155, now=10).calibrated_threshold is None
    # Голова неподвижна 20 с - база 150, глубина берётся из ручного порога: 230 - 150 = 80
    assert detector.update(152, now=20).calibrated_threshold is None
    assert detector.base_y == 150

    # Пользователь сел ниже - база сдвигается, глубина сохраняется
    detector.update(170, now=30)
    result = detector.update(170, now=50)
    assert detector.base_y == 170
    assert result.calibrated_threshold == 250
    assert detector.threshold == 250


def test_no_calibration_while_sitting():
    detector = SitDetector(threshold=200, auto_calibrate=True, calibration_seconds=20)
    for t in range(0, 60, 5):
        assert detector.update(260, now=t).calibrated_threshold is None
    assert detector.base_y is None


def test_manual_threshold_changes_depth_after_calibration():
    detector = SitDetector(threshold=230, auto_calibrate=True, calibration_seconds=20)
    detector.update(150, now=0)
    detector.update(150, now=20)
    detector.set_threshold(-200)  # Знак не важен: слайдер отдаёт отрицательные значения
    assert detector.threshold == 200
    detector.update(170, now=30)
    assert detector.update(170, now=50).calibrated_threshold == 220  # 170 + новая глубина 50
