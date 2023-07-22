import enum

PORT = 4320
SERVER_START_KEYWORD = "start"
VERSION = "1.3.0a"


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
class Rq(enum.IntEnum):
    """
    Enum for request types.

    A request is a message sent by a player asking to move, shoot, etc.
    """

    UP = enum.auto()
    DOWN = enum.auto()
    SHOOT = enum.auto()
