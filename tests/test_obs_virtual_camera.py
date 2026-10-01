"""
Проверка с настоящей виртуальной камерой OBS: кадр уходит в "OBS Virtual Camera"
и читается обратно через DirectShow - так же, как его видит OBS.
Запуск: uv run pytest --obs. Нужен установленный OBS Studio с выключенной собственной виртуальной камерой.
Во время теста источник "OBS Virtual Camera" в OBS показывает тестовую картинку
"""

import threading
import time

import cv2
import numpy as np
import pytest

from infrastructure.camera.virtual_camera import VirtualCameraOutput

pytestmark = pytest.mark.obs

OBS_DEVICE_NAME = "OBS Virtual Camera"
WIDTH, HEIGHT = 640, 480


def obs_device_index() -> int | None:
    from pygrabber.dshow_graph import FilterGraph

    names = FilterGraph().get_input_devices()
    return names.index(OBS_DEVICE_NAME) if OBS_DEVICE_NAME in names else None


def quadrants() -> np.ndarray:
    """Узнаваемая картинка: красный, зелёный, синий и белый квадранты (BGR)"""
    image = np.zeros((HEIGHT, WIDTH, 3), np.uint8)
    image[: HEIGHT // 2, : WIDTH // 2] = (0, 0, 255)
    image[: HEIGHT // 2, WIDTH // 2 :] = (0, 255, 0)
    image[HEIGHT // 2 :, : WIDTH // 2] = (255, 0, 0)
    image[HEIGHT // 2 :, WIDTH // 2 :] = (255, 255, 255)
    return image


def read_device(index: int, frames: int = 30) -> np.ndarray | None:
    capture = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, WIDTH)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, HEIGHT)
    image = None
    try:
        for _ in range(frames):
            ok, frame = capture.read()
            if ok:
                image = frame
            time.sleep(0.03)
    finally:
        capture.release()
    return image


def test_frames_reach_obs_virtual_camera():
    index = obs_device_index()
    if index is None:
        pytest.skip("OBS Virtual Camera не установлена")

    errors: list[str] = []
    output = VirtualCameraOutput(on_error=errors.append)
    pattern = quadrants()
    stop = threading.Event()

    def produce():
        while not stop.is_set():
            output.send(pattern, fps=30)
            time.sleep(1 / 30)

    producer = threading.Thread(target=produce, daemon=True)
    producer.start()
    try:
        # Подключаемся, когда кадры уже идут: сессия DirectShow, открытая без источника, кадров не получает
        deadline = time.monotonic() + 3
        while not output.is_open and not errors and time.monotonic() < deadline:
            time.sleep(0.05)
        assert output.is_open, errors
        time.sleep(0.3)
        image = read_device(index)
    finally:
        stop.set()
        producer.join()
        output.close()

    assert not errors, errors
    assert image is not None, "OBS Virtual Camera не отдаёт кадры"
    image = cv2.resize(image, (WIDTH, HEIGHT))
    # Цвет конвертируется в YUV и обратно - допускаем небольшую погрешность
    assert float(np.abs(image.astype(int) - pattern.astype(int)).mean()) < 5


def test_no_frames_without_producer():
    """Пока приложение ничего не отправляет, устройство не отдаёт кадров - значит, источник кадров - мы"""
    index = obs_device_index()
    if index is None:
        pytest.skip("OBS Virtual Camera не установлена")
    image = read_device(index, frames=10)
    assert image is None or image.max() == 0
