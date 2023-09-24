"""The part of the server that handles game-specific logic."""

import asyncio
import math
import logging
import random
from typing import Any

import aioconsole
import numpy as np

import base_shapes
import bbutils
import collisions
import constants
import server_network
import utils_3d


class Tank(base_shapes.Shape, constants.Tank):
    def __init__(self, angle, color, ground_hw, name, pos):
        super().__init__()

        self.bangle = angle  # base angle
        self.tangle = angle  # turret angle
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

        self.speed = 0.0  # m / s, I hope

        self.actions: set[constants.Action] = set()

    def recv_hit(self, damage):
        """Decrement the tank health by damage."""
        self.hits_left -= damage

    def snap_logic(self, target_angle, approaching_angle, incr):
        """
        Perform calculations for the snapping and turning back animations.

        Returns the increment to be added to the approaching angle (which may be 0)
        and a boolean indicating whether the animation has finished.

        incr should be delta times either self.SNAP_SPEED or self.BROTATE.
        """
        diff = approaching_angle - target_angle
        # once within a certain threshold of the correct angle, stop snapping back
        if abs(diff) <= incr:
            return diff, True

        if approaching_angle < target_angle:
            return incr, False
        return -incr, False

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
            # TODO: implement mine spawning
            pass

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

        if constants.Action.SHOOT in self.actions:
            # TODO: implement shell spawning
            pass

        if constants.Action.SNAP_BACK in self.actions:
            self.snapping_back = True

        if constants.Action.STOP in self.actions and abs(self.speed) <= self.SNAP_STOP:
            self.speed = 0.0

        # handle snapping/turning back
        if self.snapping_back and ip_tangle == 0.0:
            ip_tangle, finished = self.snap_logic(
                self.bangle, self.tangle, delta * self.SNAP_SPEED
            )
            if finished:
                self.snapping_back = False
        if self.turning_back and ip_bangle == 0.0:
            ip_bangle, finished = self.snap_logic(
                self.tangle, self.bangle, delta * self.BROTATE
            )
            if finished:
                self.turning_back = False

        # adjust base and turret angles and out vectors if they've changed
        if ip_bangle:
            self.bangle += ip_bangle * delta
        if ip_tangle:
            self.tangle += ip_tangle * delta

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

    @property
    def bout(self):
        # don't know if this is correct - will need some trial and error
        return utils_3d.yaw(self.bangle, np.array((1.0, 0.0, 0.0)), np.array((0.0, 0.0, 1.0)))

    @property
    def tout(self):
        # don't know if this is correct - will need some trial and error
        return utils_3d.yaw(self.tangle, np.array((1.0, 0.0, 0.0)), np.array((0.0, 0.0, 1.0)))

    @property
    def bright(self):
        return utils_3d.normalize(np.cross(constants.UP, self.bout))

    # TODO: if these vectors are actually left instead of right, rename them
    @property
    def tright(self):
        return utils_3d.normalize(np.cross(constants.UP, self.tout))


class Server:
    def __init__(self) -> None:
        self.server = server_network.ServerNetwork(self)

    async def initialize(self) -> None:
        """Code that should go in __init__ but needs to be awaited."""
        await self.server.initialize(self.listen_for_start)

    def collisions(self) -> None:
        """Check for and handle all shape collisions."""
        # not implemented yet
        return

        # check for collisions
        for hill in hills:
            # tank vs. hill
            if collide_hill(player, hill, False, player.bout):
                # Calculate a vector away from the hill. Does that make sense? :P
                # away = utils_3d.normalize(hill.pos - player.pos)
                away = utils_3d.normalize(player.pos - hill.pos)

                # back up the player so they aren't permanently stuck
                player.pos += away * 10
                player.speed = 0.0

            # shell vs. hill
            for shell in shells:
                if collide_hill(shell, hill, is_shell=True):
                    shell.hill()

        for shell in playershells:
            pos = shell.pos.copy()
            pos[1] = 0.0
            pos = DummyPos(pos)
            for tank in tanks:
                if (
                    collide_tank(pos, tank, tank.bout)
                    and (not shell.hit_hill)
                    and (shell.name != tank.name)
                ):
                    explosion.play()
                    shell.die()

        for mine in mines:
            for tank in tanks:
                if collide_mine(mine, tank, tank.bout) and mine.name != tank.name:
                    mine.die()
                    deadmine_id = mine.id

        for tree in trees:
            for tank in tanks + [player]:
                if collide_tank(tree, tank, tank.bout) and not tree.falling.any():
                    tree.fall(tank.bright, tank.speed)

        for tank in tanks:
            if collide_tanktank(tank, player, tank.bout, player.bout):
                crash.play()

                bad_tank = offender(tank, player)
                if bad_tank.name == tank.name:
                    tank.pos -= tank.bout * COLLISION_SPRINGBACK
                    player.pos += tank.bout * COLLISION_SPRINGBACK
                    for hill in hills:
                        if collide_hill(tank, hill, False, tank.bout):
                            tank.pos += tank.bout * COLLISION_SPRINGBACK
                        if collide_hill(player, hill, False, player.bout):
                            player.pos -= tank.bout * COLLISION_SPRINGBACK
                else:
                    player.pos -= player.bout * COLLISION_SPRINGBACK
                    tank.pos += player.bout * COLLISION_SPRINGBACK
                    for hill in hills:
                        if collide_hill(tank, hill, False, tank.bout):
                            tank.pos = (20 + COLLISION_SPRINGBACK) * utils_3d.normalize(
                                tank.pos - hill.pos
                            ) + hill.pos
                        if collide_hill(player, hill, False, player.bout):
                            player.pos = (
                                20 + COLLISION_SPRINGBACK
                            ) * utils_3d.normalize(player.pos - hill.pos) + hill.pos
                for tree in trees:
                    if collide_tank(tree, tank, tank.bout) and not tree.falling.any():
                        tree.fall(bad_tank.bright, 0.5)
                    if collide_tank(tree, player, tank.bout) and not tree.falling.any():
                        tree.fall(bad_tank.bright, 0.5)
                tank.speed = 0.0
                player.speed = 0.0

        for shell in shells:
            for i in range(len(shell.pos)):
                if shell.pos[i] > game.ground_hw or shell.pos[i] < -game.ground_hw:
                    shell.hill()

    def handle_request(self, client_id, actions) -> None:
        """Handle a message of type constants.Msg.REQUEST."""
        print(f"set {client_id} actions to {actions}")
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

        ground_hw, hill_poses, tree_poses, states = self.setup_env()
        # Tanks indexed by client_id
        self.tanks: dict[int, Tank] = {}
        for client_id, state in states:
            self.tanks[client_id] = Tank(
                state["angle"], state["color"], ground_hw, state["name"], state["pos"]
            )

        # inform the network server that the game has started
        self.server.start_game()

        # broadcast a START message
        self.server.message_all(
            {
                "type": constants.Msg.START,
                "states": [(client_id, t.state) for client_id, t in self.tanks.items()],
                "ground_hw": ground_hw,
                "hill_poses": hill_poses,
                "tree_poses": tree_poses,
            }
        )

        asyncio.create_task(self.send_updates())

        print("The game has started!")

    async def send_updates(self) -> None:
        # TODO: This will still cause an error for slow clients. This function should wait for all clients to send a message called STARTED.
        await asyncio.sleep(0.05)
        while True:
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
            # TODO: make a constant for this magic number
            await asyncio.sleep(0.05)

    def setup_env(
        self,
    ) -> tuple[
        int, list[tuple[float]], list[tuple[float]], list[tuple[int, dict[str, Any]]]
    ]:
        """
        Calculate the ground width, hill poses, tree poses, and tank states.

        Returns ground half width, hill poses, tree poses, and tank states.
        """
        ground_area = constants.AREA_PER_PLAYER * len(self.server.clients)
        # half the width of the ground
        # useful because currently the origin is in the middle of the ground
        # TODO: put the origin at one of the corners to simplify math
        ground_hw = int(round(math.sqrt(ground_area) / 2))

        hill_poses: list[tuple] = [
            # (x, y, z)
            (
                random.uniform(
                    -ground_hw + constants.HILL_BUFFER,
                    ground_hw - constants.HILL_BUFFER,
                ),
                0.0,
                random.uniform(
                    -ground_hw + constants.HILL_BUFFER,
                    ground_hw - constants.HILL_BUFFER,
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
                        -ground_hw + constants.TREE_BUFFER,
                        ground_hw - constants.TREE_BUFFER,
                    ),
                    0.0,
                    random.uniform(
                        -ground_hw + constants.TREE_BUFFER,
                        ground_hw - constants.TREE_BUFFER,
                    ),
                )
                valid = True
                for hill_pos in hill_poses:
                    if collisions.collide_hill(np.array(pos), np.array(hill_pos)):
                        valid = False
                        break
            return pos

        tree_poses: list[tuple] = [
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
                pos = (random.uniform(-ground_hw, ground_hw), 0.0, random.uniform(-ground_hw, ground_hw))
                valid = True
                # can't be hitting a hill
                for hill_pos in hill_poses:
                    if collisions.collide_hill(pos, hill_pos):
                        valid = False
                        break
                # can't be too close to a tank
                if valid:
                    for tank_pos in tank_poses:
                        if utils_3d.mag(np.array(pos) - np.array(tank_pos)) < constants.MIN_SPAWN_DIST:
                            valid = False
                            break
            tank_poses.append(pos)
            return pos

        # tank_poses is modified by _gen_tank_pos
        tank_poses: list[tuple[int]] = []
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

        return (ground_hw, hill_poses, tree_poses, states)


async def main() -> None:
    server = Server()
    await server.initialize()


if __name__ == "__main__":
    logger = logging.getLogger("websockets")
    logger.setLevel(logging.INFO)
    logging.root.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler())

    asyncio.run(main())
