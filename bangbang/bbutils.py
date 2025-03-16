import json
import typing

import websockets.asyncio.client
import websockets.asyncio.server

import constants

Message = typing.NewType("Message", dict)


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
        # APPROVE must have id, state
        case constants.Msg.APPROVE:
            for must_have in ("id", "state"):
                if must_have not in message:
                    raise ValueError(f"APPROVE message does not have {must_have}")

        # ID must have id
        case constants.Msg.ID if "id" not in message:
            raise ValueError("ID message does not have id")

        # GREET must have name
        case constants.Msg.GREET if "name" not in message:
            raise ValueError("GREET message does not have name")

        # MINE must have id, pos
        case constants.Msg.MINE:
            for must_have in ("id", "pos"):
                if must_have not in message:
                    raise ValueError(f"MINE message does not have {must_have}")

        # REQUEST must have actions
        case constants.Msg.REQUEST if "actions" not in message:
            raise ValueError("REQUEST message does not have actions")

        # SHELL must have angle, id, pos
        case constants.Msg.SHELL:
            for must_have in ("angle", "id", "pos"):
                if must_have not in message:
                    raise ValueError(f"SHELL message does not have {must_have}")

        # SHELL_DIE must have explo, shell_id
        case constants.Msg.SHELL_DIE:
            for must_have in ("explo", "shell_id"):
                if must_have not in message:
                    raise ValueError(f"SHELL_DIE message does not have {must_have}")

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


class BBClientProtocol(_BBSharedProtocol, websockets.asyncio.client.ClientConnection):
    pass


class BBServerProtocol(_BBSharedProtocol, websockets.asyncio.server.ServerConnection):
    pass
