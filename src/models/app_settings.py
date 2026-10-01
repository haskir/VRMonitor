import json
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

from loguru import logger

from consts import BASE_THRESHOLD

from .camera_mode import CameraMode
from .game_settings import GameSettings, HoldOrPress, Setting

__all__ = ["AppSettings"]

# Рядом с exe писать нельзя, если программа лежит в Program Files, поэтому храним в профиле пользователя
SETTINGS_PATH = Path(os.environ.get("APPDATA", Path.home())) / "VRMonitor" / "settings.json"


@dataclass
class AppSettings:
    angle_threshold: int = BASE_THRESHOLD
    sit_enabled: bool = True
    sit_y: int = 0  # Порог приседа в пикселях, 0 - не задан
    auto_calibrate: bool = False
    visualize: bool = False
    only_in_game: bool = True  # Нажимать клавиши только когда игра на переднем плане
    virtual_cam: bool = False  # Вывод картинки в виртуальную камеру OBS
    virtual_cam_mesh: bool = True
    camera_index: int | None = None
    camera_mode: CameraMode | None = None  # None - режим камеры по умолчанию
    game: GameSettings = field(default_factory=GameSettings.default)

    @classmethod
    def load(cls, path: Path = SETTINGS_PATH) -> "AppSettings":
        """Загружает настройки; при отсутствии или порче файла возвращает значения по умолчанию"""
        if not path.is_file():
            return cls()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            known = {f.name for f in fields(cls)} - {"game", "camera_mode"}
            settings = cls(**{k: v for k, v in data.items() if k in known})
            if mode := data.get("camera_mode"):
                settings.camera_mode = CameraMode(**mode)
            if game := data.get("game"):
                defaults = GameSettings.default()
                settings.game = GameSettings(
                    **{
                        name: Setting(button=s["button"], hold_or_press=HoldOrPress(s["hold_or_press"]))
                        if (s := game.get(name))
                        else getattr(defaults, name)
                        for name in ("left", "right", "sit")
                    }
                )
            return settings
        except Exception as e:
            logger.error(f"Не удалось прочитать настройки {path}, использую значения по умолчанию: {e}")
            return cls()

    def save(self, path: Path = SETTINGS_PATH):
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as e:
            logger.error(f"Не удалось сохранить настройки {path}: {e}")
