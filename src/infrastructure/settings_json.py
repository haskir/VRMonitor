import json
import os
from dataclasses import asdict, fields
from pathlib import Path
from typing import Any

from loguru import logger

from domain.bindings import Action, GameBindings, KeyBinding, KeyMode
from domain.camera import CameraMode
from domain.settings import AppSettings

__all__ = ["SETTINGS_PATH", "JsonSettingsRepository"]

# Рядом с exe писать нельзя, если программа лежит в Program Files, поэтому храним в профиле пользователя
SETTINGS_PATH = Path(os.environ.get("APPDATA", Path.home())) / "VRMonitor" / "settings.json"

# До версии с bindings привязки хранились в "game", а режим - русской подписью из интерфейса
_LEGACY_MODES = {"Удержание": KeyMode.HOLD, "Нажатие": KeyMode.PRESS}


def _parse_binding(data: dict[str, Any]) -> KeyBinding:
    mode = KeyMode(data["mode"]) if "mode" in data else _LEGACY_MODES[data["hold_or_press"]]
    return KeyBinding(button=data["button"], mode=mode)


def _parse_bindings(data: dict[str, Any]) -> GameBindings:
    bindings = GameBindings.default()
    for action in Action:
        if raw := data.get(action.value):
            bindings = bindings.with_binding(action, _parse_binding(raw))
    return bindings


class JsonSettingsRepository:
    def __init__(self, path: Path = SETTINGS_PATH):
        self._path = path

    def load(self) -> AppSettings:
        """Загружает настройки; при отсутствии или порче файла возвращает значения по умолчанию"""
        if not self._path.is_file():
            return AppSettings()
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            plain = {f.name for f in fields(AppSettings)} - {"bindings", "camera_mode"}
            settings = AppSettings(**{k: v for k, v in data.items() if k in plain})
            if mode := data.get("camera_mode"):
                settings.camera_mode = CameraMode(**mode)
            if bindings := data.get("bindings") or data.get("game"):
                settings.bindings = _parse_bindings(bindings)
            return settings
        except Exception as e:
            logger.error(f"Не удалось прочитать настройки {self._path}, использую значения по умолчанию: {e}")
            return AppSettings()

    def save(self, settings: AppSettings):
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(asdict(settings), ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError as e:
            logger.error(f"Не удалось сохранить настройки {self._path}: {e}")
