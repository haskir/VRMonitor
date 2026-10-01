import pytest

from application.game_keys import GameKeys
from application.input_controller import InputController
from domain.pose import Lean, Stance
from tests.fakes import FakeClock, FakeGameWindow, RecordingKeySender, ToggleCrouchGame


class Harness:
    """Игра с переключателем приседа и опросом раз в 250 мс, как в приложении"""

    def __init__(self):
        self.clock = FakeClock()
        self.game = ToggleCrouchGame(self.clock)
        self.window = FakeGameWindow()
        self.controller = InputController(GameKeys(self.game), self.window, self.game, clock=self.clock)
        self.controller.set_running(True)

    def run(self, seconds: float):
        for _ in range(round(seconds / 0.25)):
            self.clock.advance(0.25)
            self.controller.poll()


@pytest.fixture
def h() -> Harness:
    harness = Harness()
    harness.run(1)
    return harness


def test_sit_presses_once(h):
    h.controller.set_sitting(True)
    h.run(2)
    assert (h.game.taps, h.game.stance) == (1, Stance.CROUCH)


def test_fast_toggling_does_not_double_press(h):
    h.controller.set_sitting(True)
    h.clock.advance(0.1)
    h.controller.set_sitting(False)
    h.clock.advance(0.1)
    h.controller.set_sitting(True)
    h.clock.advance(0.1)
    h.controller.set_sitting(False)
    h.run(3)
    assert (h.game.taps, h.game.stance) == (4, Stance.STAND)


def test_manual_crouch_is_reverted_to_camera(h):
    h.controller.set_sitting(False)
    h.game.tap("C")  # Игрок присел сам
    h.run(3)
    assert (h.game.taps, h.game.stance) == (2, Stance.STAND)


def test_prone_blocks_sit(h):
    h.controller.set_sitting(False)
    h.game.set_stance(Stance.PRONE)
    h.run(1)
    assert h.controller.stance == Stance.PRONE
    h.controller.set_sitting(True)
    h.run(1)
    h.controller.set_sitting(False)
    h.run(1)
    assert (h.game.taps, h.game.stance) == (0, Stance.PRONE)


def test_leaving_prone_follows_camera(h):
    h.controller.set_sitting(False)
    h.game.set_stance(Stance.PRONE)
    h.run(1)
    h.game.set_stance(Stance.CROUCH)  # Игрок сам поднялся в присед
    h.run(3)
    assert (h.game.taps, h.game.stance) == (1, Stance.STAND)


def test_keys_only_in_game():
    clock = FakeClock()
    sender = RecordingKeySender()
    window = FakeGameWindow(active=False)
    controller = InputController(GameKeys(sender), window, ToggleCrouchGame(clock), clock=clock)
    controller.set_lean(Lean.LEFT)
    assert sender.events == []

    window.active = True
    controller.poll()
    assert sender.events == [("down", "Q")]

    window.active = False
    controller.poll()
    assert sender.events == [("down", "Q"), ("up", "Q")]  # Ушли из игры - отпустили зажатое

    controller.set_only_in_game(False)
    assert sender.events[-1] == ("down", "Q")


def test_events_for_ui():
    clock = FakeClock()
    game = ToggleCrouchGame(clock)
    window = FakeGameWindow(active=False)
    controller = InputController(GameKeys(game), window, game, clock=clock)
    active, stances = [], []
    controller.game_active_changed.connect(active.append)
    controller.stance_changed.connect(stances.append)
    controller.set_running(True)

    window.active = True
    for _ in range(3):
        controller.poll()
    window.active = False
    controller.poll()
    assert active == [True, False]
    assert stances == [Stance.STAND, None]
