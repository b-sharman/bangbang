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

# height at which gluLookAt is called
CAMERA_HEIGHT = 6.0  # m
# how far 2D elements are drawn from the camera for gluUnProject
OVERLAY_DISTANCE = 0.001  # m

# network constants
PORT = 4320
SERVER_START_KEYWORD = "start"
VERSION = "1.3.0a"

# how often to send keypresses to the server
INPUT_CHECK_WAIT = 0.005  # s

# which way is up? I guess I chose the Y dimension for whatever reason
UP = np.array((0, 1, 0), dtype=float)


class Explosion:
    NO_FRAMES = 150
    SECONDS_PER_FRAME = 0.02  # S


class Ground:
    COLOR = (0.1, 0.3, 0.0)
    POS = (0, 0, 0)


class Hill:
    COLOR = (0.1, 0.3, 0.0)

    # for collisions
    # how far a tank backs up after hitting a hill
    COLLIDE_DIST = 10  # m
    RADIUS = 20  # m


class LifeBar:
    MARGIN = 50  # px
    UNIT = 200  # px

class Mine:
    # time interval between beep noises
    BEEP_INTERVAL = 1  # s
    LIFETIME = 6  # s
    RELOAD_TIME = 2  # s

    DAMAGE = 2

    # for collisions
    RADIUS = 2


class MineExplosion:
    NO_FRAMES = 50


class ReloadingBar:
    HEIGHT = 10.0  # px
    COLOR = (0.3, 0.05, 0.0)


class Shell:
    # how many hits does this weapon deal to a Tank upon contact?
    DAMAGE = 1
    RELOAD_TIME = 10  # s
    HILL_TIME = 3  # s
    SPEED = 100.0  # m/s

    COLOR = (0.7, 0.7, 0.7)
    EXPLO_COLOR = (1.0, 0.635, 0.102)

    START_DISTANCE = 10.2  # m
    START_HEIGHT = 4.1  # m


class Spectator:
    HEIGHT = 20.0  # m

    SPEED = 20.0  # m/s
    FAST_SPEED = 40.0  # m/s
    # speed of rising animation after death
    RISE_SPEED = 30  # m/s
    # how fast to turn when left or right arrow keys are pressed
    ROTATE_SPEED = 60  # deg / s


class Tree:
    ACC = 200.0  # deg/s**2
    COLOR = (0.64, 0.44, 0.17)


class VictoryBanner:
    # final scale factor at the end of the animation
    FINAL_SCALE = 1.0
    # length of the zoom animation
    ZOOM_DURATION = 0.3  # s
    # scale of the banner at the beginning of the animation
    ZOOM_SCALE = 20.0  # at the beginning
    DIFF_SCALE = FINAL_SCALE - ZOOM_SCALE


class Tank:
    # how fast the turret rotates after the player presses "t"
    SNAP_SPEED = 600  # deg / s

    BROTATE = 45  # deg / s
    TROTATE = 90  # deg / s

    # the range in which "s" stops the tank
    SNAP_STOP = 1.5  # m/s

    # Speeds
    # 1 OGL unit = 1.74 meter
    # real M1 Abrams acceleration: 2.22
    ACC = 2.0  # m/s**2
    # real M1 Abrams max speed: 35.0
    MAX_SPEED = 10.0  # m/s
    MIN_SPEED = -4.0  # m/s

    # how many shell hits before dead?
    # TODO: rename this since a single mine hit does two damage
    HITS_TO_DIE = 5

    # for collisions
    RADIUS = 4  # m
    COLLISION_SPHERE_BACK = 4.625
    COLLISION_SPHERE_FRONT = 3.75
    COLLISION_SPRINGBACK = 5.0  # m


# raises ValueError if message types share a duplicate value
@enum.unique
class Msg(enum.IntEnum):
    """Enum for message types."""

    APPROVE = enum.auto()  # server broadcasts approval to a REQUEST
    GREET = enum.auto()    # client informs server of name, maybe color, etc.
    ID = enum.auto()       # server informs client of assigned id
    MINE = enum.auto()     # special APPROVE for mine firing
    REQUEST = enum.auto()  # client requests server to move, shoot, etc.
    SHELL = enum.auto()    # special APPROVE for shell firing
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
    SHELL = enum.auto()
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
    ((K_SPACE,), Action.SHELL),
    ((K_t,), Action.SNAP_BACK),
    ((K_s,), Action.STOP),
)
