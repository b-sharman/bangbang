import time

class Timer:
    """Class to keep track of elapsed time between two update calls."""

    def __init__(self):
        self.clock = time.time()

    def delta_time(self):
        """
        Return the time elapsed in seconds since the last call to delta_time.

        If delta_time is being called for the first time, return the time since
        __init__ was called.
        """
        new_time = time.time()
        diff = new_time - self.clock
        self.clock = new_time
        return diff


class Shape(Timer):
    gllist = "Unknown"

    def __init__(self):
        super().__init__()
        self.alive = True

    def die(self):
        self.alive = False


