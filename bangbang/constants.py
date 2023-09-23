import contextlib
import enum

import numpy as np
# hides pygame contribute message
with contextlib.redirect_stdout(None):
    from pygame.constants import *

# determines the size of the ground
AREA_PER_PLAYER = 125000  # m^2
# tree and hill densities
AREA_PER_HILL = 20800  # m^2 / hill
AREA_PER_TREE = 8333  # m^2 / tree
# minimum distance between a hill and the edge of the ground
HILL_BUFFER = 30  # m
# minimum distance between a tree and the edge of the ground
TREE_BUFFER = 0  # m
# minimum spawning distance between tanks
MIN_SPAWN_DIST = 50  # m

# network constants
PORT = 4320
SERVER_START_KEYWORD = "start"
VERSION = "1.3.0a"

# how often to send keypresses to the server
INPUT_CHECK_WAIT = 0.005  # s

# which way is up? I guess I chose the Y dimension for whatever reason
UP = np.array((0, 1, 0), dtype=float)


class Tank:
    """Class that stores tank constants."""
    # how fast the turret rotates after the player presses "t"
    SNAP_SPEED = 60.0  # deg / s

    BROTATE = 3
    TROTATE = 2

    # the range in which "s" stops the tank
    SNAP_STOP = 0.13  # m/s

    # Speeds
    # 1 OGL unit = 1.74 meter
    # real M1 Abrams acceleration: 2.22
    ACC = 2.0  # m/s**2
    # real M1 Abrams max speed: 35.0
    MAX_SPEED = 10.0  # m/s
    MIN_SPEED = -4.0  # m/s

    RELOAD_TIME = 10  # s
    # how many shell hits before dead?
    # TODO: rename this since a single mine hit does two damage
    HITS_TO_DIE = 5


# raises ValueError if message types share a duplicate value
@enum.unique
class Msg(enum.IntEnum):
    """Enum for message types."""

    APPROVE = enum.auto()  # server broadcasts approval to a REQUEST
    GREET = enum.auto()    # client informs server of name, maybe color, etc.
    ID = enum.auto()       # server informs client of assigned id
    REQUEST = enum.auto()  # client requests server to move, shoot, etc.
    START = enum.auto()    # game starts


@enum.unique
class Action(enum.IntEnum):
    """Enum for action types (e.g. accelerate, shoot, turn left, etc.)."""

    ACCEL = enum.auto()
    ALL_LEFT = enum.auto()  # both base and turret turn simulatenously
    ALL_RIGHT = enum.auto()  # both base and turret turn simulatenously
    BASE_LEFT = enum.auto()
    BASE_RIGHT = enum.auto()
    DEACCEL = enum.auto()
    MINE = enum.auto()
    TURN_BACK = enum.auto()
    TURRET_LEFT = enum.auto()
    TURRET_RIGHT = enum.auto()
    SHOOT = enum.auto()
    SNAP_BACK = enum.auto()
    STOP = enum.auto()


KEYMAP: tuple[tuple[[tuple[int], Action]]] = (
    ((K_UP,), Action.ACCEL),
    ((K_LEFT,), Action.ALL_LEFT),
    ((K_RIGHT,), Action.ALL_RIGHT),
    ((K_LCTRL, K_LEFT), Action.BASE_LEFT),
    ((K_RCTRL, K_LEFT), Action.BASE_LEFT),
    ((K_LCTRL, K_RIGHT), Action.BASE_RIGHT),
    ((K_RCTRL, K_RIGHT), Action.BASE_RIGHT),
    ((K_DOWN,), Action.DEACCEL),
    ((K_b,), Action.MINE),
    ((K_LCTRL, K_t), Action.TURN_BACK),
    ((K_RCTRL, K_t), Action.TURN_BACK),
    ((K_LSHIFT, K_LEFT), Action.TURRET_LEFT),
    ((K_RSHIFT, K_LEFT), Action.TURRET_LEFT),
    ((K_LSHIFT, K_RIGHT), Action.TURRET_RIGHT),
    ((K_RSHIFT, K_RIGHT), Action.TURRET_RIGHT),
    ((K_SPACE,), Action.SHOOT),
    ((K_t,), Action.SNAP_BACK),
    ((K_s,), Action.STOP),
)
