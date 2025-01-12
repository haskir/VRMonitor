from dataclasses import dataclass
from enum import StrEnum

import pyautogui
import cv2
import numpy as np

from consts import DEBUG

@dataclass(slots=True)
class Region:
    x: int
    y: int
    width: int
    height: int

    def to_tuple(self):
        return self.x, self.y, self.width, self.height


class CharacterState(StrEnum):
    STAND = "stand"
    SIT = "sit"
    LIE = "lie"


class PUBGCharacterController:
    THRESHOLD = 0.5  # Adjusted threshold for better matching

    def __init__(self, templates=None):
        if templates is None:
            templates = {
                "stand": "templates/stand.png",
                "sit": "templates/sit.png",
                "lie": "templates/lie.png",
            }

        self._state = None
        self.orb = cv2.ORB.create()
        self.resolution = pyautogui.size()

        self.templates = {
            state: cv2.imread(template, cv2.IMREAD_GRAYSCALE)
            for state, template in templates.items()
        }

    @classmethod
    def _calculate_icon_position(cls, resolution: tuple[int, int]) -> Region:
        """ Вычисляет положение и размер иконки для нового разрешения. """
        base_icon = Region(x=930, y=1300, width=70, height=65)
        base_width, base_height = 2560, 1440
        new_width, new_height = resolution

        scale_x = new_width / base_width
        scale_y = new_height / base_height

        return Region(
            x=int(base_icon.x * scale_x),
            y=int(base_icon.y * scale_y),
            width=int(base_icon.width * scale_x),
            height=int(base_icon.height * scale_y),
        )

    @classmethod
    def _make_screenshot(cls, region: Region):
        screenshot = pyautogui.screenshot(region=region.to_tuple())
        screenshot = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2GRAY)
        if DEBUG:
            cv2.imshow("screenshot", screenshot)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

        return screenshot

    def update_state(self):
        """
        Обновляет текущее состояние персонажа.
        """
        region = self._calculate_icon_position((2560, 1440))
        screenshot = self._make_screenshot(region)

        for state, template in self.templates.items():
            similarity = self._match_orb(screenshot, template)
            print(f"{state}: {similarity}")
            if similarity < self.THRESHOLD:
                self._state = state

        print(f"state: {self._state}")

    def _match_orb(self, image1: np.ndarray, image2: np.ndarray) -> float:
        """Сравнение двух изображений с помощью ORB."""
        # Нахождение ключевых точек и дескрипторов
        keypoints1, descriptors1 = self.orb.detectAndCompute(image1, None)
        keypoints2, descriptors2 = self.orb.detectAndCompute(image2, None)

        if descriptors1 is None or descriptors2 is None:
            return float('inf')  # Если не найдено ключевых точек

        # Сравнение дескрипторов с помощью BFMatcher
        bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        matches = bf.match(descriptors1, descriptors2)

        # Чем меньше среднее расстояние, тем лучше совпадение
        distances = [match.distance for match in matches]
        return np.mean(distances) if distances else float('inf')

    @property
    def state(self):
        return self._state


# Пример использования:
def main():
    controller = PUBGCharacterController()
    controller.update_state()
    current_state = controller.state
    print(f"Текущее состояние персонажа: {current_state}")


if __name__ == "__main__":
    main()
