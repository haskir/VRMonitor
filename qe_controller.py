import time

from pynput.keyboard import Controller, Key

q = Q = "q"
e = E = "e"


class QEController:
    def __init__(self):
        self.keyboard = Controller()
        self._q = False
        self._e = False

    def press_q(self):
        if self._e:
            self.release_e()
        self._q = True
        self.keyboard.press(q)

    def release_q(self):
        if self._q:
            self._q = False
            self.keyboard.release(q)

    def press_e(self):
        if self._q:
            self.release_q()
        self._e = True
        self.keyboard.press(e)

    def release_e(self):
        if self._e:
            self._e = False
            self.keyboard.release(e)

    def release_all(self):
        self.release_q()
        self.release_e()
