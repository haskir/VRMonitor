from pynput.keyboard import Controller

q = Q = "q"
e = E = "e"


class KeyboardController:
    def __init__(self):
        self.keyboard = Controller()
        self._is_on = False
        self._q = False
        self._e = False

    def press_q(self):
        if not self._is_on:
            return
        if self._e:
            self.release_e()
        self._q = True
        self.keyboard.press(q)

    def release_q(self):
        if self._q:
            self._q = False
            self.keyboard.release(q)

    def press_e(self):
        if not self._is_on:
            return
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

    def on(self):
        self._is_on = True

    def off(self):
        self._is_on = False
        self.release_all()