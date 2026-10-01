from dataclasses import replace

from application.game_keys import GameKeys
from domain.bindings import GameBindings, KeyBinding, KeyMode
from domain.pose import Lean
from tests.fakes import RecordingKeySender


def make_keys(**bindings: KeyBinding) -> tuple[GameKeys, RecordingKeySender]:
    """Привязки по умолчанию (Q/E удержание, C нажатие) с заменой указанных"""
    sender = RecordingKeySender()
    return GameKeys(sender, replace(GameBindings.default(), **bindings)), sender


def test_hold_lean_switches_sides():
    keys, sender = make_keys()
    keys.set_lean(Lean.LEFT)
    keys.set_lean(Lean.RIGHT)
    keys.set_lean(Lean.NONE)
    assert sender.events == [("down", "Q"), ("up", "Q"), ("down", "E"), ("up", "E")]
    assert keys.lean == Lean.NONE


def test_press_lean_toggles_twice():
    keys, sender = make_keys(left=KeyBinding("Q", KeyMode.PRESS))
    keys.set_lean(Lean.LEFT)
    keys.set_lean(Lean.NONE)
    assert sender.events == [("tap", "Q"), ("tap", "Q")]


def test_sitting_is_idempotent():
    keys, sender = make_keys()
    keys.set_sitting(True)
    keys.set_sitting(True)
    keys.set_sitting(False)
    assert sender.events == [("tap", "C"), ("tap", "C")]


def test_release_held_keeps_toggles():
    keys, sender = make_keys(sit=KeyBinding("C", KeyMode.HOLD))
    keys.set_lean(Lean.LEFT)
    keys.set_sitting(True)
    sender.events.clear()
    keys.release_held()
    assert sender.events == [("up", "Q"), ("up", "C")]
    assert keys.lean == Lean.NONE and not keys.is_sitting

    keys, sender = make_keys(left=KeyBinding("Q", KeyMode.PRESS))
    keys.set_lean(Lean.LEFT)
    keys.set_sitting(True)
    sender.events.clear()
    keys.release_held()
    assert sender.events == []  # Переключатели не трогаем - нажатие ушло бы в чужое окно
    assert keys.lean == Lean.LEFT and keys.is_sitting


def test_assume_sitting_only_for_toggle():
    keys, sender = make_keys()
    assert keys.assume_sitting(True)
    assert keys.is_sitting
    assert not keys.assume_sitting(True)

    keys, sender = make_keys(sit=KeyBinding("C", KeyMode.HOLD))
    assert not keys.assume_sitting(True)
    assert not keys.is_sitting
    assert sender.events == []
