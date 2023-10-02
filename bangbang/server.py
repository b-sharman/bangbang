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
from shapes import HeadlessMine, HeadlessShell
import utils_3d

# TODO: add consistent type hinting throughout the whole project


# TODO: rename this class to HeadlessTank and move it to shapes.py
class Tank(base_shapes.Shape, constants.Tank):
    def __init__(self, angle, client_id, color, ground_hw, name, pos, server):
        super().__init__()

        self.bangle = angle  # base angle
        self.tangle = angle  # turret angle
        self.client_id = client_id
        self.color = color
        self.ground_hw = ground_hw
        self.name = name
        self.pos = np.array(pos)

        # snapping back: turret turns to meet base
        # turning back: base turns to meet turret
        # these variables are true if either t or ctrl t have been pressed
        # I believe they can both be true simulatneously
        self.snapping_back = False
        self.turning_back = False

        self.hits_left: int = self.HITS_TO_DIE  # how many more hits before dead?
        self.mine_reloading = 0  # timestamp at which tank can lay a mine again
        self.shell_reloading = 0  # timestamp at which tank can fire a shell again
        self.speed = 0.0  # m / s, I hope

        self.actions: set[constants.Action] = set()

        self.server = server

    def recv_hit(self, damage: int) -> None:
        """Decrement the tank health by damage."""
        self.hits_left -= damage
        if self.hits_left <= 0:
            self.die()

    def snap_logic(self, target_angle, approaching_angle, incr):
        """
        Perform calculations for the snapping and turning back animations.

        Returns the increment to be added to the approaching angle (which may be 0)
        and a boolean indicating whether the animation is still going.

        incr should be delta * (self.SNAP_SPEED or self.BROTATE).
        """
        diff = approaching_angle - target_angle
        # the sign of the increment
        direction = (diff < 0) - (diff > 0)
        diff = abs(diff)
        # always choose the shortest path
        if diff > 180.0:
            diff = 360 - diff
            direction *= -1

        # once within a certain threshold of the correct angle, stop snapping back
        if diff <= incr:
            return diff * direction, False
        return incr * direction, True

    def update(self):
        delta = self.delta_time()

        ip_bangle = 0
        ip_tangle = 0

        # TODO: ask some knowledgeable folks whether a match-case pattern would be more
        # appropriate here
        if constants.Action.ACCEL in self.actions:
            self.speed = min(self.speed + self.ACC * delta, self.MAX_SPEED)

        if constants.Action.ALL_LEFT in self.actions:
            self.turning_back = False
            self.snapping_back = False
            ip_bangle = self.BROTATE
            ip_tangle = self.BROTATE

        if constants.Action.ALL_RIGHT in self.actions:
            self.turning_back = False
            self.snapping_back = False
            ip_bangle = -self.BROTATE
            ip_tangle = -self.BROTATE

        if constants.Action.BASE_LEFT in self.actions:
            # cancel turning back upon manual turn
            self.turning_back = False
            ip_bangle = self.BROTATE

        if constants.Action.BASE_RIGHT in self.actions:
            # cancel turning back upon manual turn
            self.turning_back = False
            ip_bangle = -self.BROTATE

        if constants.Action.DEACCEL in self.actions:
            self.speed = max(self.speed - self.ACC * delta, self.MIN_SPEED)

        if constants.Action.MINE in self.actions:
            if self.clock >= self.mine_reloading + constants.Mine.RELOAD_TIME:
                self.mine_reloading = self.clock
                self.server.make_mine(self.client_id, self.pos)

        if constants.Action.TURN_BACK in self.actions:
            self.turning_back = True

        if constants.Action.TURRET_LEFT in self.actions:
            # cancel snapping back upon manual turn
            self.snapping_back = False
            ip_tangle = self.TROTATE

        if constants.Action.TURRET_RIGHT in self.actions:
            # cancel snapping back upon manual turn
            self.snapping_back = False
            ip_tangle = -self.TROTATE

        if constants.Action.SHELL in self.actions:
            if self.clock >= self.shell_reloading + constants.Shell.RELOAD_TIME:
                self.shell_reloading = self.clock
                self.server.make_shell(
                    self.tangle,
                    self.client_id,
                    self.tout + (self.bout * self.speed / constants.Shell.SPEED),
                    self.pos + constants.Shell.START_DISTANCE * self.tout,
                )

        if constants.Action.SNAP_BACK in self.actions:
            self.snapping_back = True

        if constants.Action.STOP in self.actions and abs(self.speed) <= self.SNAP_STOP:
            self.speed = 0.0

        # snap_logic returns the number of degrees to turn this frame; all the other
        # logic specifies the rate of turning in degrees per second
        if not self.snapping_back:
            ip_tangle *= delta
        if not self.turning_back:
            ip_bangle *= delta

        # handle snapping/turning back
        if self.snapping_back and ip_tangle == 0.0:
            ip_tangle, self.snapping_back = self.snap_logic(
                self.bangle, self.tangle, self.SNAP_SPEED * delta
            )
        if self.turning_back and ip_bangle == 0.0:
            ip_bangle, self.turning_back = self.snap_logic(
                self.tangle, self.bangle, self.BROTATE * delta
            )

        # adjust base and turret angles and out vectors if they've changed
        if ip_bangle:
            self.bangle += ip_bangle
        if ip_tangle:
            self.tangle += ip_tangle

        # make sure the angles don't get too high, this helps the turret animation
        self.bangle %= 360.0
        self.tangle %= 360.0

        # move the tank, according to the speed
        self.pos += self.bout * self.speed * delta
        # ensure the tank does not go over the edge of the world
        self.pos[0] = max(min(self.pos[0], self.ground_hw), -self.ground_hw)
        self.pos[2] = max(min(self.pos[2], self.ground_hw), -self.ground_hw)

    @property
    def state(self):
        # TODO: make this dynamically change to not send already-known data
        return {
            "bangle": self.bangle,
            "color": self.color,
            "hits_left": self.hits_left,
            "name": self.name,
            "pos": tuple(self.pos),
            "speed": self.speed,
            "tangle": self.tangle,
        }

    # vector properties

    # TODO: this is duplicated code from client.PlayerData - find a way to reuse it
    @property
    def bout(self):
        # don't know if this is correct - will need some trial and error
        return utils_3d.yaw(self.bangle, np.array((0.0, 0.0, 1.0)), np.array((1.0, 0.0, 0.0)))

    @property
    def tout(self):
        # don't know if this is correct - will need some trial and error
        return utils_3d.yaw(self.tangle, np.array((0.0, 0.0, 1.0)), np.array((1.0, 0.0, 0.0)))

    # TODO: if these vectors are actually left instead of right, rename them
    @property
    def bright(self):
        return utils_3d.normalize(np.cross(constants.UP, self.bout))


class Server:
    def __init__(self) -> None:
        self.server = server_network.ServerNetwork(self)

    async def initialize(self) -> None:
        """Code that should go in __init__ but needs to be awaited."""
        await self.server.initialize(self.listen_for_start)

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

        for hill_pos in self.hill_poses:
            # tank vs. hill
            for tank in self.tanks.values():
                if collisions.collide_hill_tank(hill_pos, tank.pos, tank.bout):
                    print("tank hit hill")
                    # back up the tank away from the hill so they aren't permanently stuck
                    tank.pos += utils_3d.normalize(tank.pos - hill_pos) * constants.Hill.COLLIDE_DIST
                    tank.speed = 0.0

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
                    shell.die()
                    # TODO: make some sort of network signal to tell clients to play a "shell hit" sound

        for mine in self.mines:
            for tank in self.tanks.values():
                if tank.client_id == mine.client_id and collisions.collide_tank_mine(tank.pos, mine.pos, tank.bout) and mine.name != tank.name:
                    print(f"mine hit tank {tank.client_id}")
                    tank.recv_hit(constants.Mine.DAMAGE)
                    mine.die()

    def handle_request(self, client_id, actions) -> None:
        """Handle a message of type constants.Msg.REQUEST."""
        # Isn't it expensive to make new sets? Perhaps a new datatype should
        # be used for Tank.actions
        self.tanks[client_id].actions = set(actions)

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
        # TODO: This will still cause an error for slow clients. This function should wait for all clients to send a message called STARTED.
        await asyncio.sleep(0.05)
        while True:
            self.collisions()
            # TODO: maybe self.tanks should be list[tuple[int, Tank]] instead of dict[int, Tank]?
            for client_id, tank in self.tanks.items():
                tank.update()
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
            # TODO: make a constant for this magic number
            await asyncio.sleep(0.05)

    def setup_env(
        self,
    ) -> tuple[
        int, list[tuple[float]], list[tuple[float]], list[tuple[int, dict[str, Any]]]
    ]:
        """
        Returns ground half width and tank states.
        Sets self.self.hill_poses and self.self.tree_poses.
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
