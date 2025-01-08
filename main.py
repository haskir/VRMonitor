import os
import sys
import time
from pprint import pprint
from venv import logger

import cv2
import mediapipe as mp
import numpy as np

import cameras_provider
from qe_controller import QEController
from windows_provider import WindowsProvider


class CameraController:
    def __init__(self, cap: cv2.VideoCapture, qe_controller: QEController, threshold: int,
                 window_cont: WindowsProvider):
        self.cap = cap
        self.qe_controller = qe_controller
        self.threshold = threshold
        self.window_cont = window_cont

    @classmethod
    def _calculate_head_tilt(cls, landmarks):
        """
        Функция для вычисления угла наклона головы
        """
        # Координаты глаз
        left_eye = np.array([(landmarks[33][0], landmarks[33][1])])  # Левый глаз
        right_eye = np.array([(landmarks[263][0], landmarks[263][1])])  # Правый глаз

        # Координаты носа (верхняя точка)
        # nose_tip = np.array([(landmarks[1][0], landmarks[1][1])])

        # Вычисление угла между глазами
        dx = right_eye[0][0] - left_eye[0][0]
        dy = right_eye[0][1] - left_eye[0][1]
        angle = np.degrees(np.arctan2(dy, dx))
        return angle

    def _is_sufficient_angle(self, angle: float) -> bool:
        return abs(angle) > self.threshold

    @classmethod
    def get_text_to_display(cls, angle: float) -> str:
        # Определение направления наклона
        if angle > 10:
            return f"Head tilt to the left ({angle:.2f})"
        elif angle < -10:
            return f"Head tilt to the right ({angle:.2f})"
        else:
            return f"Head is straight ({angle:.2f})"

    @classmethod
    def put_text_to_window(cls, text: str, frame, color: tuple[int, int, int] = None):
        """
        Функция для отображения направления наклона на экране
        """
        cv2.putText(
            frame,
            text=text,
            org=(10, 30),
            fontFace=cv2.FONT_HERSHEY_SIMPLEX,
            fontScale=0.7,
            color=color if color else (255, 255, 255)
        )

    def run(self):
        logger.info(f'Запуск камеры {self.cap}')

        # Инициализация Mediapipe
        mp_face_mesh = mp.solutions.face_mesh
        face_mesh = mp_face_mesh.FaceMesh()
        while self.cap.isOpened():
            time.sleep(0.03)
            try:
                ret, frame = self.cap.read()
                if not ret:
                    break
                # Преобразуем изображение в RGB (требуется Mediapipe)
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                # Обнаружение лица
                results = face_mesh.process(rgb_frame)

                if results.multi_face_landmarks:
                    for face_landmarks in results.multi_face_landmarks:
                        if not self.window_cont.is_target_active:
                            break

                        # Извлечение координат ключевых точек лица
                        landmarks = [(lm.x * frame.shape[1], lm.y * frame.shape[0]) for lm in face_landmarks.landmark]
                        # Вычисление угла наклона
                        angle = self._calculate_head_tilt(landmarks)

                        if self._is_sufficient_angle(angle):
                            self.qe_controller.press_q() if angle > 0 else self.qe_controller.press_e()
                        else:
                            self.qe_controller.release_all()

                        # Визуализация точек лица
                        for x, y in landmarks:
                            cv2.circle(frame, (int(x), int(y)), 1, (0, 255, 255), -1)

                        self.put_text_to_window(
                            self.get_text_to_display(angle),
                            frame,
                            (255, 255, 255) if not abs(angle) > 10 else (255, 0, 0) if angle > 0 else (0, 255, 0)
                        )

                # Показываем изображение
                cv2.imshow("Head Tilt Detection", frame)

                # Выход из программы по нажатию клавиши "]"
                if cv2.waitKey(1) & 0xFF == ord(']'):
                    break
            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.error(f"Произошла ошибка: {e}")
                time.sleep(1)


def main():
    cameras = cameras_provider.CameraProvider.get_available_cameras_ids()
    if not cameras:
        exit("Нет доступных камер.")
    print(f"Доступные камеры: {cameras}")
    cap = cv2.VideoCapture(cameras[0])

    window_finder = WindowsProvider()
    windows = window_finder.all_windows()
    pprint(windows)
    # inp = int(input(f"Выберите окно: от -1 до {len(windows) - 1}\n"))
    inp = -1
    for i, window in windows.items():
        if "PUBG" in window:
            inp = i
    window_finder.set_target(windows[inp])

    camera_controller = CameraController(cap, QEController(), THRESHOLD, window_finder)
    camera_controller.run()
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    os.chdir(os.path.split(sys.argv[0])[0])
    THRESHOLD: int = 16
    main()
