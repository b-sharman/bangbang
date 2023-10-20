"""The part of the server that handles game-specific logic."""

import asyncio
import math
import logging
import random
import time
from typing import Any

import aioconsole
import numpy as np

import base_shapes
import bbutils
import collisions
import constants
import server_network
from shapes import HeadlessMine, HeadlessShell, HeadlessTank
import utils_3d

# TODO: add consistent type hinting throughout the whole project

class Tank(HeadlessTank):
    def __init__(self, angle, client_id, color, ground_hw, name, pos, server):
        super().__init__(angle, client_id, color, ground_hw, name, pos)

        self.mine_reloading = 0  # timestamp at which tank can lay a mine again
        self.shell_reloading = 0  # timestamp at which tank can fire a shell again

        # whether a tank state change has occurred that needs to be sent to the clients
        self.__needs_update = False
        self.server = server

    def update(self) -> bool:
        super().update()

        if constants.Action.MINE in self.actions:
            if self.clock >= self.mine_reloading + constants.Mine.RELOAD_TIME:
                self.mine_reloading = self.clock
                self.server.make_mine(self.client_id, self.pos)

        if constants.Action.SHELL in self.actions:
            if self.clock >= self.shell_reloading + constants.Shell.RELOAD_TIME:
                self.shell_reloading = self.clock
                self.server.make_shell(
                    self.tangle,
                    self.client_id,
                    self.tout + (self.bout * self.speed / constants.Shell.SPEED),
                    self.pos + constants.Shell.START_DISTANCE * self.tout,
                )

        temp_needs_update = self.__needs_update
        self.__needs_update = False
        return temp_needs_update

    def update_actions(self, actions: set) -> None:
        self.__needs_update = True
        self.actions = actions

    def set_needs_update(self) -> None:
        """Make this Tank send a network update on the next call to update()."""
        self.__needs_update = True


class Server:
    def __init__(self) -> None:
        self.end_event = asyncio.Event()
        self.server = server_network.ServerNetwork(self)

    async def initialize(self) -> None:
        """Code that should go in __init__ but needs to be awaited."""
        await self.server.initialize(self.listen_for_start, self.end_event)

    def collisions(self) -> None:
        """Check for and handle all shape collisions."""
        # tank-tank collisions
        # this should be first in case the tank back up causes another collision
        already_checked: list[set[Tank, Tank]] = []
        for tank1 in self.tanks.values():
            for tank2 in self.tanks.values():
                pair = {tank1, tank2}
                if tank1 == tank2 or pair in already_checked:
                    continue
                if collisions.collide_tank_tank(tank1.pos, tank2.pos, tank1.bout, tank2.bout):
                    # TODO: make some sort of network signal to tell clients to play a "tank1 collide" sound

                    # move the tanks away from each other
                    print(f"tank {tank1.client_id} hit tank {tank2.client_id}")
                    away = utils_3d.normalize(tank1.pos - tank2.pos) * constants.Tank.COLLISION_SPRINGBACK
                    tank1.pos += away
                    tank2.pos -= away
                    tank1.speed = 0.0
                    tank2.speed = 0.0
                    already_checked.append(pair)
                    tank1.set_needs_update()
                    tank2.set_needs_update()

        for hill_pos in self.hill_poses:
            # tank vs. hill
            for tank in self.tanks.values():
                if collisions.collide_hill_tank(hill_pos, tank.pos, tank.bout):
                    print("tank hit hill")
                    # back up the tank away from the hill so they aren't permanently stuck
                    tank.pos += utils_3d.normalize(tank.pos - hill_pos) * constants.Hill.COLLIDE_DIST
                    tank.speed = 0.0
                    tank.set_needs_update()

            # shell vs. hill
            # Trust the client to also check for shell-hill collisions to
            #   A) minimize complexity of the network protocol and
            #   B) avoid the need for shells to have unique IDs
            for shell in self.shells:
                if collisions.collide_hill(hill_pos, shell.pos):
                    print("shell hit hill")
                    shell.die()

        for shell in self.shells:
            # remove shells exiting the playing area
            if collisions.collide_shell_world(shell.pos, self.ground_hw):
                print("shell hit world")
                shell.die()
                break

            # handle tank-shell collisions
            for tank in self.tanks.values():
                if tank.client_id != shell.client_id and collisions.collide_tank(tank.pos, np.array((shell.pos[0], 0.0, shell.pos[2])), tank.bout):
                    print(f"shell hit tank {tank.client_id}")
                    tank.recv_hit(constants.Shell.DAMAGE)
                    tank.set_needs_update()
                    shell.die()
                    # TODO: make some sort of network signal to tell clients to play a "shell hit" sound

        for mine in self.mines:
            for tank in self.tanks.values():
                if tank.client_id != mine.client_id and collisions.collide_tank_mine(tank.pos, mine.pos, tank.bout):
                    print(f"mine hit tank {tank.client_id}")
                    tank.recv_hit(constants.Mine.DAMAGE)
                    tank.set_needs_update()
                    mine.die()

    def handle_request(self, client_id, actions) -> None:
        """Handle a message of type constants.Msg.REQUEST."""
        # Isn't it expensive to make new sets? Perhaps a new datatype should
        # be used for Tank.actions
        self.tanks[client_id].update_actions(set(actions))

    async def listen_for_start(self) -> None:
        """Start the game upon receiving proper user input."""
        print(f"Type '{constants.SERVER_START_KEYWORD}' at any time to start the game.")

        output = None
        while output != constants.SERVER_START_KEYWORD:
            output = await aioconsole.ainput()
            # how many players have not submitted their names yet?
            # I think this should be faster than list comp. in terms of number of
            # iterations and memory required
            nameless_count = 0
            for c in self.server.clients:
                # adds 1 to nameless count if the name is None
                nameless_count += c.name is None
            if nameless_count > 0:
                # cannot start until all players have submitted names
                print(
                    f"Cannot start; {nameless_count} {'players have' if nameless_count > 1 else 'player has'} not submitted their name"
                )
                # do not exit the while loop
                output = None

        states = self.setup_env()
        # Tanks indexed by client_id
        self.tanks: dict[int, Tank] = {}
        for client_id, state in states:
            self.tanks[client_id] = Tank(
                state["angle"],
                client_id,
                state["color"],
                self.ground_hw,
                state["name"],
                state["pos"],
                self,
            )
        self.mines: list[HeadlessMine] = []
        self.shells: list[HeadlessShell] = []

        # inform the network server that the game has started
        self.server.start_game()

        # broadcast a START message
        self.server.message_all(
            {
                "type": constants.Msg.START,
                "states": [(client_id, t.state) for client_id, t in self.tanks.items()],
                "ground_hw": self.ground_hw,
                "hill_poses": self.hill_poses,
                "tree_poses": self.tree_poses,
            }
        )

        asyncio.create_task(self.send_updates())

        print("The game has started!")

    def make_mine(self, client_id: int, pos: np.ndarray) -> None:
        self.mines.append(HeadlessMine(client_id, pos))
        self.server.message_all(
            {
                "type": constants.Msg.MINE,
                "id": client_id,
                "pos": tuple(pos),
            }
        )

    def make_shell(self, angle: float, client_id: int, out: np.ndarray, pos: np.ndarray) -> None:
        self.shells.append(HeadlessShell(angle, client_id, out, pos))
        self.server.message_all(
            {
                "type": constants.Msg.SHELL,
                "id": client_id,
                "angle": angle,
                "out": tuple(out),
                "pos": tuple(pos),
            }
        )

    async def send_updates(self) -> None:
        end_time = None
        while end_time is None or time.time() < end_time:
            self.collisions()
            # TODO: maybe self.tanks should be list[tuple[int, Tank]] instead of dict[int, Tank]?
            for client_id, tank in self.tanks.items():
                # tank.update() returns whether a network update is necessary
                if tank.update():
                    print(f"sending update for tank {client_id}")
                    self.server.message_all(
                        {
                            "type": constants.Msg.APPROVE,
                            "id": client_id,
                            "state": tank.state,
                        }
                    )

            for shell in self.shells:
                shell.update()
            for mine in self.mines:
                mine.update()
            # remove objects with .alive = False
            self.tanks = {client_id: tank for client_id, tank in self.tanks.items() if tank.alive}
            self.mines = [m for m in self.mines if m.alive]
            self.shells = [s for s in self.shells if s.alive]

            # check for a winner
            if len(self.tanks) == 1 and not hasattr(self, "winner"):
                self.winner = tuple(self.tanks.values())[0]
                print(f"{self.winner.name} ({self.winner.client_id}) won")
                end_time = time.time() + constants.END_TIME

            # allow other coroutines (including networking) to take place
            await asyncio.sleep(0)

        # after we exit the while loop, we must exit the whole program
        self.end_event.set()

    def setup_env(
        self,
    ) -> tuple[
        int, list[tuple[float]], list[tuple[float]], list[tuple[int, dict[str, Any]]]
    ]:
        """
        Returns ground half width and tank states.
        Sets self.hill_poses and self.tree_poses.
        """
        ground_area = constants.AREA_PER_PLAYER * len(self.server.clients)
        # half the width of the ground
        # useful because currently the origin is in the middle of the ground
        # TODO: put the origin at one of the corners to simplify math
        self.ground_hw = int(round(math.sqrt(ground_area) / 2))

        self.hill_poses: list[tuple] = [
            # (x, y, z)
            (
                random.uniform(
                    -self.ground_hw + constants.HILL_BUFFER,
                    self.ground_hw - constants.HILL_BUFFER,
                ),
                0.0,
                random.uniform(
                    -self.ground_hw + constants.HILL_BUFFER,
                    self.ground_hw - constants.HILL_BUFFER,
                ),
            )
            for _ in range(
                # the number of hills
                int(round(ground_area / constants.AREA_PER_HILL))
            )
        ]

        def _gen_tree_pos():
            valid = False
            while not valid:
                pos = (
                    random.uniform(
                        -self.ground_hw + constants.TREE_BUFFER,
                        self.ground_hw - constants.TREE_BUFFER,
                    ),
                    0.0,
                    random.uniform(
                        -self.ground_hw + constants.TREE_BUFFER,
                        self.ground_hw - constants.TREE_BUFFER,
                    ),
                )
                valid = True
                for hill_pos in self.hill_poses:
                    if collisions.collide_hill(np.array(pos), np.array(hill_pos)):
                        valid = False
                        break
            return pos

        self.tree_poses: list[tuple] = [
            _gen_tree_pos()
            for _ in range(
                # the number of trees
                int(round(ground_area / constants.AREA_PER_TREE))
            )
        ]

        # tank states: pos, angle, color

        def _gen_tank_pos(tank_poses):
            valid = False
            while not valid:
                pos = np.array(
                    (
                        random.uniform(-self.ground_hw, self.ground_hw),
                        0.0,
                        random.uniform(-self.ground_hw, self.ground_hw)
                    )
                )
                valid = True
                # can't be hitting a hill
                for hill_pos in self.hill_poses:
                    # TODO: technically we should compute an angle and use collide_hill_tank
                    if collisions.collide_hill(np.array(hill_pos), pos):
                        valid = False
                        break
                # can't be too close to a tank
                if valid:
                    for tank_pos in tank_poses:
                        if utils_3d.mag(pos - tank_pos) < constants.MIN_SPAWN_DIST:
                            valid = False
                            break
            tank_poses.append(pos)
            return pos

        # tank_poses is modified by _gen_tank_pos
        tank_poses: list[np.ndarray[float]] = []
        states: list[tuple[int, dict[str, Any]]] = [
            (
                client.client_id,
                {
                    "angle": random.uniform(0, 360),
                    "color": [random.random() for _ in range(3)],
                    "name": client.name,
                    "pos": _gen_tank_pos(tank_poses),
                },
            )
            for client in self.server.clients
        ]

        return states


async def main() -> None:
    server = Server()
    await server.initialize()


if __name__ == "__main__":
    logger = logging.getLogger("websockets")
    logger.setLevel(logging.INFO)
    logging.root.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler())

    asyncio.run(main())
