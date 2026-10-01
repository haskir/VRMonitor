from pathlib import Path

import cv2
import numpy as np
import pytest

from domain.pose import Stance
from infrastructure.stance_detector import classify_stance, icon_region

DATA = Path(__file__).parent / "data"


def load(name: str) -> np.ndarray:
    image = cv2.imread(str(DATA / name))
    assert image is not None, name
    return image


def icon_alpha(icon: np.ndarray) -> np.ndarray:
    """Насколько пиксель белее фона - чтобы перенести силуэт на другой фон"""
    gray = cv2.cvtColor(icon, cv2.COLOR_BGR2GRAY).astype(float)
    background = np.median(gray)
    return np.clip((gray - background - 10) / (238 - background - 10), 0, 1)[..., None]


ICONS = {stance: f"icon_{stance}_1440.png" for stance in Stance}

BACKGROUNDS = {
    "dark": np.full((100, 92, 3), 40, np.uint8),
    "grass": np.dstack([np.full((100, 92), 60), np.full((100, 92), 140), np.full((100, 92), 70)]).astype(np.uint8),
    "sky": np.dstack([np.full((100, 92), 220), np.full((100, 92), 180), np.full((100, 92), 130)]).astype(np.uint8),
    "light_snow": np.clip(np.random.default_rng(0).normal(205, 8, (100, 92, 1)).repeat(3, 2), 0, 255).astype(np.uint8),
}


@pytest.mark.parametrize("stance", list(ICONS))
def test_screenshots(stance):
    assert classify_stance(load(ICONS[stance]), scale=1.0) == stance


def test_live_capture_on_grass():
    """Снимок области иконки из запущенной игры 2560x1440: персонаж стоит, позади трава"""
    assert classify_stance(load("live_stand_grass_1440.png"), scale=1.0) == Stance.STAND


@pytest.mark.parametrize("stance", list(ICONS))
def test_1080p(stance):
    small = cv2.resize(load(ICONS[stance]), None, fx=0.75, fy=0.75, interpolation=cv2.INTER_AREA)
    assert classify_stance(small, scale=0.75) == stance


@pytest.mark.parametrize("background", list(BACKGROUNDS))
@pytest.mark.parametrize("stance", list(ICONS))
def test_other_backgrounds(stance, background):
    icon = load(ICONS[stance])
    alpha = icon_alpha(icon)
    patch = cv2.resize(BACKGROUNDS[background], (icon.shape[1], icon.shape[0])).astype(float)
    composed = (patch * (1 - alpha) + 240 * alpha).astype(np.uint8)
    assert classify_stance(composed, scale=1.0) == stance


@pytest.mark.parametrize("background", list(BACKGROUNDS))
def test_no_icon(background):
    assert classify_stance(BACKGROUNDS[background], scale=1.0) is None


def test_bright_snow_is_unknown():
    """На почти белом фоне иконку не отличить - лучше честно сказать "не знаю"""
    icon = load(ICONS[Stance.STAND])
    snow = np.clip(np.random.default_rng(0).normal(232, 6, (*icon.shape[:2], 1)).repeat(3, 2), 0, 255)
    alpha = icon_alpha(icon)
    composed = (snow * (1 - alpha) + 240 * alpha).astype(np.uint8)
    assert classify_stance(composed, scale=1.0) is None


def test_region_on_full_screen():
    # Вырезка из скриншота 2000x1125, начиная с x=600, y=950
    screen = np.zeros((1125, 2000, 3), np.uint8)
    hud = load("hud_prone_2000x1125.png")
    screen[950:, 600:1400] = hud
    region = icon_region(2000, 1125)
    crop = screen[region.y : region.y + region.height, region.x : region.x + region.width]
    assert classify_stance(crop, scale=1125 / 1440) == Stance.PRONE
