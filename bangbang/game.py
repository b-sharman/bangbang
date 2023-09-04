# TODO: find it out if it makes sense to make all update() functions coroutines
import asyncio
import logging
import math
import socket
import time
import types

import aioconsole
import numpy as np
import pygame
from pygame.constants import *

from OpenGL.GL import *
from OpenGL.GLU import *

import utils_3d
import bbutils
from client import Client, PlayerData
import constants
import server
import shapes

# did we win?
won = False
# are we in spectate mode?
spectating = False

COLLISION_SPRINGBACK = 10.0  # m

# For now, pygame init needs to be here since some classes load sounds, etc. in
# their headers
#
# TODO: only initialize the pygame modules in use to speed up loading times
# https://www.pygame.org/docs/ref/pygame.html#pygame.init
pygame.init()


class Game:
    def __init__(self, no_music) -> None:
        self.client = Client(self)

        # used to block opening the window until the game has started
        self.start_event = asyncio.Event()

        self.input_handler = PlayerInputHandler(self)
        # id of the player playing on this computer
        # assigned upon receiving an ID message
        self.player_id = None

        self.players: dict[int, PlayerData] = {}

        # set width when client receives START from server
        self.ground_hw: int | None = None
        self.hill_poses: list[tuple] | None = None
        self.tree_poses: list[tuple] | None = None

        # used to avoid all_shapes, tanks, etc. cluttering the Game namespace
        # https://docs.python.org/3/library/types.html#types.SimpleNamespace
        self.groups = types.SimpleNamespace()

        self.no_music = no_music

    # TODO: replace the initialize methods with factory methods
    async def initialize(self, ip: str) -> None:
        """Things that can't go in __init__ because they're coros"""
        async with asyncio.TaskGroup() as self.tg:
            self.tg.create_task(self.client.start(ip))

            # wait until the server sends a start signal
            await self.start_event.wait()

            # run CPU-intensive code in a non-blocking way
            # https://docs.python.org/3/library/asyncio-dev.html#running-blocking-code
            await asyncio.get_running_loop().run_in_executor(None, self.initialize_graphics)

            await self.start_main_loop()

    async def assign_name(self) -> None:
        name = await aioconsole.ainput("Enter your name: ")
        await self.client.greet(name)

    async def handle_message(self, message: dict) -> None:
        """Handle a JSON-loaded dict network message."""
        match message["type"]:
            case constants.Msg.APPROVE:
                try:
                    self.players[message["id"]].update_state(message["state"])
                except KeyError:
                    logging.log(logging.DEBUG, f"received APPROVE for player {message['id']} which does not exist")
                else:
                    pass
                    # logging.debug(
                    #     f"PlayerData {message['id']} state updated with {message['state']}"
                    # )

            case constants.Msg.ID:
                self.player_id = message["id"]

            case constants.Msg.START:
                logging.debug("starting")
                for client_id, state in message["states"]:
                    self.players[client_id] = PlayerData(state)

                self.ground_hw = message["ground_hw"]
                self.hill_poses = message["hill_poses"]
                self.tree_poses = message["tree_poses"]
                for client_id, state in message["states"]:
                    self.players[client_id].update_state(state)

                # allow the main game loop to start
                self.start_event.set()
                # start listening for keyboard input
                # self.tg is defined in initialize
                self.tg.create_task(self.input_handler.run())

    def initialize_graphics(self):
        """
        Set up the pygame and OpenGL environments and generate some display lists.

        This method essentially does everything that can't be done at the very beginning
        but needs to be done before the main loop can start.
        """
        # initialize pygame to display OpenGL
        screen = pygame.display.set_mode(flags=OPENGL | DOUBLEBUF | FULLSCREEN | HWSURFACE)
        SCR = (screen.get_width(), screen.get_height())

        # hide the mouse
        pygame.mouse.set_visible(False)

        # start music ASAP if the user wants it
        if not self.no_music:
            pygame.mixer.music.load("../data/sound/theme.mp3")
            pygame.mixer.music.play(-1)  # play the theme song on loop

        # set the window title
        pygame.display.set_caption("Bang Bang " + constants.VERSION)

        # enable depth and turn on lights
        glEnable(GL_DEPTH_TEST)
        glEnable(GL_LIGHT0)
        glEnable(GL_LIGHTING)

        # position the sun in an "afternoon" position for best tank lighting
        glLightfv(GL_LIGHT0, GL_POSITION, (self.ground_hw * 0.5, 300.0, self.ground_hw * 0.5))

        # turn on colors
        glColorMaterial(GL_FRONT, GL_DIFFUSE)
        glEnable(GL_COLOR_MATERIAL)

        # set up the camera lens
        glMatrixMode(GL_PROJECTION)
        if not gluPerspective:
            logging.warning("If the program crashes, make sure glew is installed.")
        gluPerspective(
            45.0,
            float(SCR[0]) / float(SCR[1]),
            0.1,
            # length of the ground diagonal, which is the longest distance the player would need to see
            math.sqrt(8) * self.ground_hw,
        )
        glMatrixMode(GL_MODELVIEW)

        # set up the explosion displaylists
        shapes.setup_explosion()

        # NATURE

        # make the sky blue
        glClearColor(0.25, 0.89, 0.92, 1.0)

        ground = shapes.Ground(self.ground_hw)
        lifebar = shapes.LifeBar(self.players[self.player_id], SCR)
        # reloading is the time at which the player can fire again
        # it must be defined here since ReloadingBar accesses it
        self.reloading = time.time()
        self.reloadingbar = shapes.ReloadingBar(SCR[0], self)

        self.groups.hills = [shapes.Hill(pos) for pos in self.hill_poses]
        self.groups.trees = [shapes.Tree(pos) for pos in self.tree_poses]
        self.groups.tanks = [shapes.Tank(self, client_id) for client_id in self.players]
        self.groups.shells = []
        self.groups.mines = []

        # Make all_shapes
        self.groups.all_shapes = [ground, lifebar, self.reloadingbar] + self.groups.hills + self.groups.trees + self.groups.tanks + self.groups.shells + self.groups.mines

        # TODO: implement a reloading timer for dropping mines
        # It should probably not be implemented here in the main loop, but that's where
        # this comment is because it used to be implemented here

    async def start_main_loop(self):
        # timestamp of the final frame
        end_time = None

        frame_length = -1.0
        frame_end_time = time.time()

        while end_time is None or frame_end_time < end_time:
            frame_start_time = frame_end_time

            # listen for input device events
            pygame.event.pump()

            # print FPS to the console when the F key is pressed
            if pygame.key.get_pressed()[pygame.K_f]:
                print(f"{int(round(1 / frame_length))} FPS")

            # quit game on window close or escape key
            if pygame.event.get(pygame.QUIT) or pygame.key.get_pressed()[pygame.K_ESCAPE]:
                # end right now
                # this breaks out of the while loop
                end_time = frame_start_time

            # clear everything
            glLoadIdentity()
            glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)

            # set up the observer
            # choose the camera attributes based on whether we're playing or spectating
            # TODO; How expensive is hasattr? It could be replaced by a
            # self.is_spectating variable or a class that stores just the pos and out
            # of either the player or the spectator.
            if hasattr(self, "spectator"):
                pos = self.spectator.pos
                out = self.spectator.out
            else:
                pos = np.array(self.player_data.pos)
                # TODO: define a constant for this magic number
                pos[1] = 6.0
                out = np.array(self.player_data.tout)
                at = out + pos
            gluLookAt(*pos, *at, *constants.UP)

            for shape in self.groups.all_shapes:
                shape.update()

            # make bullet on space
            # TODO: move this to the server
            if (
                pygame.key.get_pressed()[pygame.K_SPACE]
                and self.reloading < time.time()
                and self.player_data.alive
                and end_time is None
            ):
                # TODO: Wouldn't it be cleaner to move this code either to
                # Shell.__init__ or a Shell factory function?
                temp_tout = np.array(self.player_data.tout) + (np.array(player.bout) * player.speed) / Shell.SPEED
                temp_pos = np.array(self.player_data.pos) + Shell.START_DISTANCE * np.array(
                    self.player_data.tout
                )
                shell = Shell(temp_pos, temp_tout, self.player_data.tangle, "Gandalf")
                self.groups.shells.append(shell)
                self.groups.all_shapes.append(shell)

                # set reloading bar to full
                self.reloadingbar.fire()

                self.reloading = time.time() + server.Tank.RELOAD_TIME

            # TODO: add networking to this
            if pygame.key.get_pressed()[pygame.K_b] and self.player_data.alive and end_time is None:
                pass
                # mine = Mine(player.name, player.pos, player.color)
                # mines.append(mine)
                # all_shapes.append(mine)
                # mine_reload = Mine.RELOAD

                # if (not won) and (not hasattr(self, "spectator")):
                #     self.spectator = Spectator(
                #         player.pos, player.tout, constants.UP, player.tright, player.tangle
                #     )
                #     self.groups.all_shapes.append(self.spectator)
                # # TODO: simplify this confusing endgame logic
                # if (len(tanks) == 1) or won:
                #     end_time = frame_start_time + 3
                #     pygame.mixer.music.fadeout(3000)

            pygame.display.flip()

            frame_end_time = time.time()
            frame_length = frame_end_time - frame_start_time

        # close the pygame window
        pygame.quit()

    @property
    def player_data(self) -> PlayerData:
        return self.players[self.player_id]


class PlayerInputHandler:
    """Sends keyboard input to the server."""

    def __init__(self, game: Game) -> None:
        self.game = game

        # the value of pygame.key.get_pressed last frame
        self.prev_keymap = pygame.key.get_pressed()

        # to avoid sending the same set of actions twice in a row
        self.prev_actions = None

    async def run(self) -> None:
        """Interface to send requests to the server."""
        keys = pygame.key.get_pressed()
        actions: list[constants.Action] = [
            action
            for key_combo, action in constants.KEYMAP
            if all(
                {keys[k] for k in key_combo}
            )  # if all the keys in the combo are pressed
        ]
        if actions != self.prev_actions:
            await self.game.client.send_actions(actions)
            self.prev_actions = actions

        # recursion!
        # TODO: make a constant for this magic number
        await asyncio.sleep(0.01)
        # TODO: find a way to uncomment this - currently it blocks the async loop, I'm afraid
        # await self.run()


async def main(host, no_music):
    # set up logging
    logger = logging.getLogger("websockets")
    logger.setLevel(logging.INFO)
    logging.root.setLevel(logging.DEBUG)
    logger.addHandler(logging.StreamHandler())

    print("Welcome to Bang Bang " + constants.VERSION)

    game = Game(no_music)
    try:
        await game.initialize(host)
    except (socket.gaierror, OSError):
        logging.error(f"could not connect to {host}")
        exit()
