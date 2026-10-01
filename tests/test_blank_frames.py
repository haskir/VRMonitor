import numpy as np

from infrastructure.camera.blank_frames import BlankFrameDetector

BLACK = np.zeros((480, 640, 3), np.uint8)
DARK_NOISE = np.random.default_rng(0).integers(0, 12, (480, 640, 3), dtype=np.uint8)  # Тёмный шум MJPG
NORMAL = np.full((480, 640, 3), 120, np.uint8)


def test_black_frames_after_delay():
    detector = BlankFrameDetector(blank_seconds=1.5)
    assert not detector.update(BLACK, now=0.0)
    assert not detector.update(BLACK, now=1.0)
    assert not detector.is_blank  # Камера может стартовать с нескольких тёмных кадров
    assert detector.update(BLACK, now=1.6)
    assert detector.is_blank
    assert not detector.update(DARK_NOISE, now=2.0)  # Уже чёрный - изменения нет
    assert detector.is_blank


def test_normal_frame_clears_immediately():
    detector = BlankFrameDetector(blank_seconds=1.0)
    detector.update(BLACK, now=0.0)
    detector.update(BLACK, now=1.0)
    assert detector.update(NORMAL, now=1.1)
    assert not detector.is_blank
    # Отсчёт начинается заново
    assert not detector.update(BLACK, now=1.2)
    assert not detector.update(BLACK, now=2.1)
    assert detector.update(BLACK, now=2.2)


def test_dark_scene_with_details_is_not_blank():
    detector = BlankFrameDetector(blank_seconds=0.5)
    frame = BLACK.copy()
    frame[200:260, 300:340] = 90  # Тёмная комната, но лицо видно
    for t in range(10):
        detector.update(frame, now=float(t))
    assert not detector.is_blank


def test_reset():
    detector = BlankFrameDetector(blank_seconds=0.0)
    detector.update(BLACK, now=0.0)
    assert detector.is_blank
    detector.reset()
    assert not detector.is_blank
