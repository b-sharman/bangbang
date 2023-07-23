import asyncio
import json
import websockets

import bbutils
import constants


class Client:
    def __init__(self, game: "game.Game") -> None:
        self.game = game

    async def greet(self, name: str) -> None:
        """
        Send a GREET message to the server.

        This type of message informs the server of the player name.
        """
        await self.ws.send({"type": constants.Msg.GREET, "name": name})

    async def send_rq(self, rq: constants.Rq) -> None:
        """Send an rq-type message to the server."""
        await self.ws.send({"type": constants.Msg.REQUEST, "rq": rq})

    async def start(self, ip: str) -> None:
        """Attempt to connect to the server and listen for new messages."""
        async with websockets.connect(
            f"ws://{ip}:{constants.PORT}", create_protocol=bbutils.BBClientProtocol
        ) as self.ws:
            async with asyncio.TaskGroup() as tg:
                created_name_task = False

                while True:
                    try:
                        # waits until data is received from the server
                        message = json.loads(await self.ws.recv())
                    except websockets.exceptions.ConnectionClosed:
                        if not created_name_task:
                            print(
                                "There was an error when trying to connect to the server. This probably means that the game has already started."
                            )
                        else:
                            print("The server disconnected unexpectedly.")
                        exit()

                    # placing the following block here guarantees that the "Enter your name:" text will not be displayed if there is a server error
                    if not created_name_task:
                        tg.create_task(self.game.assign_name())
                        created_name_task = True

                    await self.game.handle_message(message, tg)
