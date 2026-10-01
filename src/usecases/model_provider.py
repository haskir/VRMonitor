import urllib.request
from pathlib import Path

from loguru import logger

from consts import FACE_LANDMARKER_PATH, FACE_LANDMARKER_URL

__all__ = ["ensure_face_landmarker"]


def ensure_face_landmarker(path: Path = FACE_LANDMARKER_PATH, url: str = FACE_LANDMARKER_URL) -> Path:
    """Возвращает путь к модели, при отсутствии скачивает её"""
    if path.is_file() and path.stat().st_size > 0:
        return path

    logger.info(f"Модель не найдена, скачиваю {url} -> {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".part")
    try:
        with urllib.request.urlopen(url, timeout=30) as response, tmp_path.open("wb") as f:
            while chunk := response.read(64 * 1024):
                f.write(chunk)
        tmp_path.replace(path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise
    logger.info(f"Модель скачана: {path}")
    return path
