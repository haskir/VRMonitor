from dataclasses import dataclass, field

import cv2
from loguru import logger

from models import CameraMode

__all__ = [
    "Camera",
    "CameraMode",
    "CamerasProvider",
]

# Форматы, которые OpenCV умеет декодировать через DirectShow; H264/H265 пропускаем
SUPPORTED_FOURCC = ("MJPG", "YUY2", "NV12", "RGB24")
# Сюда мы сами выводим картинку - если читать её же, получится петля
OWN_OUTPUT_CAMERAS = ("OBS Virtual Camera",)


@dataclass
class Camera:
    index: int
    name: str
    modes: list[CameraMode] = field(default_factory=list)

    def __repr__(self):
        return f"Устройство {self.index:02d}: {self.name}"


class _Subtypes(dict):
    """pygrabber падает на неизвестных форматах (H264 и т.п.) - достаём FOURCC прямо из GUID"""

    def __missing__(self, guid: str) -> str:
        return bytes.fromhex(guid[1:9])[::-1].decode("ascii", "replace")


class CamerasProvider:
    @staticmethod
    def _test_camera(index: int) -> bool:
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        try:
            return bool(cap.read()[0])
        finally:
            cap.release()

    @classmethod
    def get_available_cameras(cls) -> list[Camera]:
        """Возвращает список работающих камер с поддерживаемыми режимами"""
        cameras = []
        for camera in cls._get_dshow_cameras():
            if camera.name in OWN_OUTPUT_CAMERAS:
                continue
            if cls._test_camera(camera.index):
                logger.info(f"{camera} - OK, режимов: {len(camera.modes)}")
                cameras.append(camera)
            else:
                logger.info(f"{camera} - не отдаёт кадры, пропускаю")

        if not cameras:
            logger.error("Нет доступных камер!")
        return cameras

    @classmethod
    def _get_dshow_cameras(cls) -> list[Camera]:
        """Камеры в порядке DirectShow - он совпадает с индексами cv2.CAP_DSHOW"""
        try:
            from pygrabber import dshow_graph

            dshow_graph.subtypes = _Subtypes(dshow_graph.subtypes)
            names = dshow_graph.FilterGraph().get_input_devices()
        except Exception as e:
            logger.error(f"Не удалось получить список камер через DirectShow: {e}")
            return [Camera(index=i, name=f"Camera {i}") for i in range(10)]

        cameras = []
        for index, name in enumerate(names):
            try:
                graph = dshow_graph.FilterGraph()
                graph.add_video_input_device(index)
                formats = graph.get_input_device().get_formats()
            except Exception as e:
                logger.error(f"Не удалось получить режимы камеры [{index}] {name}: {e}")
                formats = []
            cameras.append(Camera(index=index, name=name, modes=cls._pick_modes(formats)))
        return cameras

    @staticmethod
    def _pick_modes(formats: list[dict]) -> list[CameraMode]:
        """Для каждого разрешения оставляет режим с максимальным fps (при равенстве - MJPG)"""
        best: dict[tuple[int, int], CameraMode] = {}
        for f in formats:
            fourcc = f["media_type_str"]
            if fourcc not in SUPPORTED_FOURCC:
                continue
            # В pygrabber min_framerate считается из минимального интервала кадра, т.е. это максимальный fps
            mode = CameraMode(width=f["width"], height=f["height"], fps=round(f["min_framerate"]), fourcc=fourcc)
            current = best.get((mode.width, mode.height))
            if current is None or (mode.fps, mode.fourcc == "MJPG") > (current.fps, current.fourcc == "MJPG"):
                best[(mode.width, mode.height)] = mode
        return sorted(best.values(), key=lambda m: (m.width * m.height, m.fps), reverse=True)


if __name__ == "__main__":
    for cam in CamerasProvider.get_available_cameras():
        print(cam)
        for m in cam.modes:
            print("   ", m)
