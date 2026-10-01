from pathlib import Path

BASE_THRESHOLD = 20
TEST_CAMERA_TITLE = "Тестирование выбранной камеры"

# Окна, в которых нажимаются клавиши (если не включён режим "на всех окнах")
TARGET_GAME_NAME = "PUBG"
TARGET_PROCESSES = ("TslGame.exe",)
TARGET_TITLES = ("PUBG: BATTLEGROUNDS",)  # Запасной вариант, если процесс не удалось открыть
WINDOW_CHECK_INTERVAL_MS = 250  # Как часто проверять смену активного окна (и позу персонажа)
STANCE_SETTLE_SECONDS = 0.7  # Сколько после нажатия приседа не верить иконке позы - идёт анимация

# Авто-калибровка верхнего положения головы
CALIBRATION_SECONDS = 20  # Сколько держать голову неподвижно, чтобы принять её Y за верхнее положение
CALIBRATION_TOLERANCE = 15  # Допустимое дрожание головы по Y (в единицах Y_SCALE)
DEFAULT_SIT_DEPTH = 80  # Глубина приседа по умолчанию (в единицах Y ниже верхнего положения)

# Y головы считается в долях высоты кадра * Y_SCALE, чтобы порог не зависел от разрешения камеры
Y_SCALE = 500
CAMERA_PREVIEW_WIDTH = 960  # Начальная ширина окна предпросмотра камеры

# Работает и при запуске через `uv run`, и в собранном nuitka-бинаре
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

FACE_LANDMARKER_PATH = STATIC_DIR / "face_landmarker.task"
FACE_LANDMARKER_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
)
