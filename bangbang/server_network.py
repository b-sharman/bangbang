"""The part of the server that moves data around."""

import asyncio
from collections.abc import Coroutine
import json
import logging
import socket
import websockets
import websockets.server  # only for typing, is that bad?

import bbutils
import constants


def get_local_ip():
    """Return the computer's local IP address."""
    # based on https://stackoverflow.com/questions/166506/finding-local-ip-addresses-using-pythons-stdlib
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        # The following raises socket.error if not connected to Internet
        # Wrote a simple try-except to get around.
        try:
            s.connect(("8.8.8.8", 80))
        except (socket.error, OSError):
            raise RuntimeError("Connection didn't work; are you connected to the internet?")
        else:
            return s.getsockname()[0]


class Client:
    """Server's representation of a network client."""

    def __init__(
        self,
        s: "server.Server",
        ws: websockets.server.WebSocketServer,
        tg: asyncio.TaskGroup,
        client_id: int,
    ) -> None:
        """Warning: only create Client instances within the tg context manager."""

        self.server = s
        self.ws = ws

        # set by a REQUEST message
        self.actions = set()
        # assign this client a unique id
        self.client_id = client_id
        # set by a GREET message
        self.name = None

        # start listening to messages coming in from the client
        handler = tg.create_task(self.handler())

    async def initialize(self) -> None:
        """Code that should go in __init__ but needs to be awaited."""
        await self.ws.send({"type": constants.Msg.ID, "id": self.client_id})

    async def handler(self) -> None:
        """Listen for messages coming in from client ws."""
        async for json_message in self.ws:
            # convert JSON string to dict
            message = json.loads(json_message)
            match message["type"]:
                case constants.Msg.GREET:
                    self.name = message["name"]
                    print(f"{message['name']} has joined.")

                case constants.Msg.REQUEST:
                    self.server.handle_request(self.client_id, message["actions"])


class ServerNetwork:
    def __init__(self, s: "server.Server") -> None:
        try:
            self.ip = get_local_ip()
        except RuntimeError as m:
            logging.error(m)
            exit()

        # has the game been started yet?
        self.game_running = False

        self.clients: list[Client] = []

        self.server = s

        # the id that will be assigned to the next client
        # can't do something as simple as len(self.clients) because a client might
        # disconnect and rejoin
        self.next_id = -1

    async def initialize(self, start_func: Coroutine, end_event: asyncio.Event) -> None:
        """Code that should go in __init__ but needs to be awaited."""
        async with websockets.serve(
            self.handle_new_connection,
            self.ip,
            constants.PORT,
            create_connection=bbutils.BBServerProtocol,
            ping_interval=5,
            ping_timeout=10,
        ):
            print(f"Server started on {self.ip}:{constants.PORT}")
            await asyncio.create_task(start_func())
            # wait until end_event is set
            await end_event.wait()

    def end_game(self) -> None:
        self.game_running = False

    def get_next_id(self) -> int:
        """Return a unique integer ID for the next connected client."""
        self.next_id += 1
        return self.next_id

    async def handle_new_connection(self, ws: websockets.server.WebSocketServer) -> None:
        """Start server communications with ws and add ws to self.clients."""
        # prevent new clients from connecting if the game has already started
        if self.game_running:
            await ws.close()
            print("rejected a player because the game has already started")
            return

        async with asyncio.TaskGroup() as tg:
            # add ws to the self.clients set and remove it upon disconnect
            client = Client(self.server, ws, tg, self.get_next_id())
            await client.initialize()
            self.clients.append(client)
            logging.debug(f"added player with id {client.client_id}")
            try:
                await client.ws.wait_closed()
            finally:
                self.clients.remove(client)
                logging.debug(f"removed player with id {client.client_id}")

    def message_all(self, message: bbutils.Message) -> None:
        """Serialize message to JSON and broadcast it to all members of self.clients."""
        # check for message validity - raises ValueError if not valid
        bbutils.is_message_valid(message)

        # turn the bbutils.Message into a JSON-formated str
        data = json.dumps(message)
        websockets.broadcast([c.ws for c in self.clients], data)

    def start_game(self) -> None:
        """Call this method when the game starts."""
        self.game_running = True
