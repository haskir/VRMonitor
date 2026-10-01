from pathlib import Path

# Игра, в которую нажимаются клавиши (если не включён режим "в любом окне")
TARGET_GAME_NAME = "PUBG"
TARGET_PROCESSES = ("TslGame.exe",)
TARGET_TITLES = ("PUBG: BATTLEGROUNDS",)  # Запасной вариант, если процесс не удалось открыть
POLL_INTERVAL_MS = 250  # Как часто проверять активное окно и позу персонажа

# Работает и при запуске через `uv run`, и в собранном nuitka-бинаре
BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

FACE_LANDMARKER_PATH = STATIC_DIR / "face_landmarker.task"
FACE_LANDMARKER_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"
)
