import json

from domain.bindings import Action, GameBindings, KeyBinding, KeyMode
from domain.camera import CameraMode
from domain.settings import AppSettings
from infrastructure.settings_json import JsonSettingsRepository


def test_roundtrip(tmp_path):
    repository = JsonSettingsRepository(tmp_path / "settings.json")
    settings = AppSettings(
        angle_threshold=15,
        camera_index=2,
        camera_mode=CameraMode(1920, 1080, 60, "MJPG"),
        bindings=GameBindings.default().with_binding(Action.SIT, KeyBinding("X", KeyMode.HOLD)),
    )
    repository.save(settings)
    assert repository.load() == settings


def test_missing_or_broken_file_gives_defaults(tmp_path):
    path = tmp_path / "settings.json"
    assert JsonSettingsRepository(path).load() == AppSettings()
    path.write_text("{not json", encoding="utf-8")
    assert JsonSettingsRepository(path).load() == AppSettings()


def test_legacy_format(tmp_path):
    """Файл до переработки: привязки в "game", режим - русской подписью"""
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "angle_threshold": 25,
                "sit_y": 120,
                "unknown_field": 1,
                "game": {
                    "left": {"button": "A", "hold_or_press": "Нажатие"},
                    "right": {"button": "D", "hold_or_press": "Удержание"},
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    settings = JsonSettingsRepository(path).load()
    assert settings.angle_threshold == 25
    assert settings.sit_y == 120
    assert settings.bindings.left == KeyBinding("A", KeyMode.PRESS)
    assert settings.bindings.right == KeyBinding("D", KeyMode.HOLD)
    assert settings.bindings.sit == GameBindings.default().sit
