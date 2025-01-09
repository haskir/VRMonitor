import cv2
import win32com.client
from loguru import logger

from dataclasses import dataclass

from usecases.singleton import Singleton


@dataclass
class Camera:
    index: int
    name: str

    def __repr__(self):
        return f"Устройство {self.index:02d}: {self.name}"


class CamerasProvider(Singleton):
    def __init__(self):
        self.show = False

    @staticmethod
    def _test_camera(index: int) -> bool:
        try:
            cap = cv2.VideoCapture(index)
            ret, _ = cap.read()
            cap.release()
            if not ret:
                logger.info(f"Ошибка: Невозможно считать кадр с камеры[{index}]!")
                return False
            return True
        except Exception as e:
            logger.error(f"Ошибка при тестировании камеры[{index}]: {e}")
            return False

    @classmethod
    def get_available_cameras(cls) -> list[Camera]:
        """
        Возвращает список доступных камер.
        """
        cameras_list = []
        camera_ids = cls._get_available_cameras_ids()
        camera_names = cls._get_camera_names()

        for index in camera_ids:
            name = camera_names.get(index, f"Camera {index}")
            cameras_list.append(Camera(index=index, name=name))

        return cameras_list

    @staticmethod
    def _get_available_cameras_ids() -> list[int]:
        """
        Возвращает список индексов доступных камер.
        """
        max_cameras = 10
        available = []
        for i in range(max_cameras):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if not cap.read()[0]:
                cap.release()
                continue

            available.append(i)
            cap.release()
            logger.info(f"Camera {i:02d} is OK!")

        if not available:
            logger.error("Нет доступных камер!")
        return available

    @staticmethod
    def _get_camera_names() -> dict[int, str]:
        """
        Получает имена камер с помощью Windows API.
        """
        camera_names = {}
        try:
            obj = win32com.client.Dispatch("WbemScripting.SWbemLocator")
            svc = obj.ConnectServer(".", "root\\CIMV2")
            col_items = svc.ExecQuery("Select * from Win32_PnPEntity")

            index = 0
            for item in col_items:
                if "USB" in item.Name or "Camera" in item.Name or "Webcam" in item.Name:
                    camera_names[index] = item.Name
                    index += 1
        except TypeError:
            pass
        except Exception as e:
            logger.error(f"Ошибка при получении названий камер: {type(e)} {e}")
        return camera_names


if __name__ == "__main__":
    provider = CamerasProvider()
    cameras = provider.get_available_cameras()

    if cameras:
        print("Доступные камеры:")
        for camera in cameras:
            print(f"Индекс: {camera.index}, Название: {camera.name}")
    else:
        print("Нет доступных камер!")
