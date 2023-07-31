# TODO: add type hints to the functions in this file

import json
import random
import time
import typing

import numpy as np
import websockets.client
import websockets.server

import collisions
import constants

Message = typing.NewType("Message", dict)


class Shape(object):
    """Base shape class."""

    gllist = "Unknown"

    def __init__(self):
        self.clock = time.time()
        self.alive = True

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

    def die(self):
        self.alive = False


def is_message_valid(message: Message) -> None:
    """Raise ValueError if message does not meet protocol."""
    # TODO: This is already hard to read and will only become more difficult. It might
    # be worthwhile to consider an external data validation library like cerberus.

    # must be a dict
    if not isinstance(message, dict):
        raise ValueError("message is not a dict")

    # must have type
    if "type" not in message:
        raise ValueError("message has no type")

    # type must be specified in constants.Msg
    if message["type"] not in iter(constants.Msg):
        raise ValueError("invalid message type")

    # id must be int
    if "id" in message and not isinstance(message["id"], int):
        raise ValueError("client id is not int")

    # name must be str
    if "name" in message and not isinstance(message["name"], str):
        raise ValueError("client name is not str")

    # actions must be specified in constants.Action
    if "actions" in message:
        for a in message["actions"]:
            if a not in iter(constants.Action):
                raise ValueError(f"invalid message action '{a}'")

    # type-specific requirements
    match message["type"]:
        case constants.Msg.APPROVE:
            # APPROVE must have id
            if "id" not in message:
                raise ValueError("APPROVE message does not have id")
            # APPROVE must have state
            if "state" not in message:
                raise ValueError("APPROVE message does not have state")

        # ID must have id
        case constants.Msg.ID if "id" not in message:
            raise ValueError("ID message does not have id")

        # GREET must have name
        case constants.Msg.GREET if "name" not in message:
            raise ValueError("GREET message does not have name")

        # REQUEST must have actions
        case constants.Msg.REQUEST if "actions" not in message:
            raise ValueError("REQUEST message does not have actions")

        # START must have ...
        case constants.Msg.START:
            for must_have in ("ground_hw", "hill_poses", "tree_poses", "states"):
                if must_have not in message:
                    raise ValueError(f"START message does not have {must_have}")


class _BBSharedProtocol:
    """WebSocketClientProtocol with send() that enforces JSON format."""

    async def send(self, message: Message) -> None:
        """
        Serialize message to json and call the regular send on it.

        This method also enforces message validity; it is decorated by
        check_message_valid.
        """
        is_message_valid(message)
        await super().send(json.dumps(message))


class BBClientProtocol(_BBSharedProtocol, websockets.client.WebSocketClientProtocol):
    pass


class BBServerProtocol(_BBSharedProtocol, websockets.server.WebSocketServerProtocol):
    pass
