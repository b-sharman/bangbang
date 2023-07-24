# TODO: find it out if it makes sense to make all update() functions coroutines
import asyncio
import math
import random
import time

import numpy as np
import pygame
from pygame.locals import *

from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *

import bbutils
from client import Client
import constants

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


def window2view(pts):
    """Convert window coordinates to 3D coordinates."""
    model = glGetDoublev(GL_MODELVIEW_MATRIX)
    projection = glGetDoublev(GL_PROJECTION_MATRIX)
    viewport = glGetIntegerv(GL_VIEWPORT)

    retval = [
        gluUnProject(pt[0], pt[1], 0.001, model, projection, viewport) for pt in pts
    ]

    return retval


def exec_raw(full_name):
    """
    Read in a triangular representation of a piece for rendering.

    Uses a custom format which is much faster than stl or ogl.gz reading.
    """

    try:
        rawdata = np.fromfile(full_name, np.float32)
    except IOError:
        print(("Couldn't find", full_name))
        exit()

    raw_length = len(rawdata) // 2
    normals = np.reshape(rawdata[raw_length:], (raw_length // 3, 3))
    vertices = np.reshape(rawdata[:raw_length], (raw_length // 3, 3))
    glEnableClientState(GL_VERTEX_ARRAY)
    glEnableClientState(GL_NORMAL_ARRAY)

    glVertexPointerf(vertices)
    glNormalPointerf(normals)
    glDrawArrays(GL_TRIANGLES, 0, len(vertices))

    glDisableClientState(GL_VERTEX_ARRAY)
    glDisableClientState(GL_NORMAL_ARRAY)


def setup_explosion():
    """Create gllists for Explosions and MineExplosions."""
    if Explosion.base_gllists == "Unknown":
        Explosion.base_gllists = []
        for i in range(1, Explosion.NO_EXPLOSION_FRAMES + 1):
            gllist = glGenLists(1)
            glNewList(gllist, GL_COMPILE)
            exec_raw(f"../data/models/explosions/base_explosion_{i:06}.raw")
            glEndList()
            Explosion.base_gllists.append(gllist)

    if Explosion.turret_gllists == "Unknown":
        Explosion.turret_gllists = []
        for i in range(1, Explosion.NO_EXPLOSION_FRAMES + 1):
            gllist = glGenLists(1)
            glNewList(gllist, GL_COMPILE)
            exec_raw(f"../data/models/explosions/turret_explosion_{i:06}.raw")
            glEndList()
            Explosion.turret_gllists.append(gllist)

    if MineExplosion.gllists == "Unknown":
        MineExplosion.gllists = []
        for i in range(1, MineExplosion.MAX_FRAMES + 1):
            gllist = glGenLists(1)
            glNewList(gllist, GL_COMPILE)
            exec_raw(f"../data/models/explosions/mine_explosion_{i:06}.raw")
            glEndList()
            MineExplosion.gllists.append(gllist)


class Tree(bbutils.Shape):
    ACC = 30.0  # degrees/s**2
    FALL_SOUND = pygame.mixer.Sound("../data/sound/tree.wav")
    hit_height = 3.0  # where the tank hits the tree

    def __init__(self, pos):
        super().__init__()
        if Tree.gllist == "Unknown":
            Tree.gllist = glGenLists(1)
            glNewList(Tree.gllist, GL_COMPILE)
            exec_raw("../data/models/tree_lowpoly.raw")
            glEndList()

        self.pos = np.array(pos)
        # set to 0 array when tree is alive and to tank.right when tree is falling
        self.falling = np.zeros(3)
        self.fall_angle = 0.0
        self.played_sound = False

    def update(self):
        delta = self.delta_time()

        glPushMatrix()
        glColor(0.64, 0.44, 0.17)
        glTranslate(*self.pos)
        if self.falling.any():
            self.speed += Tree.ACC * delta
            self.fall_angle += self.speed
            if self.fall_angle > 90:
                self.fall_angle = 90
                if not self.played_sound:
                    Tree.FALL_SOUND.play()
                    self.played_sound = True
            glRotate(self.fall_angle, *self.falling)
        glCallList(Tree.gllist)
        glPopMatrix()

    def fall(self, angle, speed):
        """Called when a tank collides with a tree."""
        if speed > 0:
            self.falling = angle
        if speed < 0:
            self.falling = -angle
        self.speed = speed / Tree.HIT_HEIGHT


class Hill(bbutils.Shape):
    def __init__(self, pos):
        if Hill.gllist == "Unknown":
            Hill.gllist = glGenLists(1)
            glNewList(Hill.gllist, GL_COMPILE)
            exec_raw("../data/models/hill2.raw")
            glEndList()

        self.pos = np.array(pos)

    def update(self):
        glPushMatrix()
        glColor(0.1, 0.3, 0.0)
        glTranslate(*self.pos)
        glCallList(Hill.gllist)
        glPopMatrix()


class Ground(bbutils.Shape):
    """A plane that serves as the ground."""

    COLOR = (0.1, 0.3, 0.0)

    # half-width
    HW = 250
    WIDTH = HW * 2
    # length of the diagonal, calculated with the Pythagorean
    DIAGONAL = math.sqrt(2 * (WIDTH**2))

    def __init__(self):
        self.pos = np.zeros(3)

    def gen_list(self):
        """Generate the gllist for the ground."""
        Ground.gllist = glGenLists(1)
        glNewList(Ground.gllist, GL_COMPILE)
        glBegin(GL_POLYGON)
        glNormal(0.0, 1.0, 0.0)
        glVertex(self.pos[0] - Ground.HW, self.pos[1], self.pos[2] - Ground.HW)
        glNormal(0.0, 1.0, 0.0)
        glVertex(self.pos[0] + Ground.HW, self.pos[1], self.pos[2] - Ground.HW)
        glNormal(0.0, 1.0, 0.0)
        glVertex(self.pos[0] + Ground.HW, self.pos[1], self.pos[2] + Ground.HW)
        glNormal(0.0, 1.0, 0.0)
        glVertex(self.pos[0] - Ground.HW, self.pos[1], self.pos[2] + Ground.HW)
        glNormal(0.0, 1.0, 0.0)
        # the last point must close the square
        glVertex(self.pos[0] - Ground.HW, self.pos[1], self.pos[2] - Ground.HW)
        glEnd()
        glEndList()

    def update(self):
        glPushMatrix()
        glColor(*Ground.COLOR)
        glTranslate(*self.pos)
        glCallList(Ground.gllist)
        glPopMatrix()


class Explosion(bbutils.Shape):
    # so that the first explosion will set up the display lists
    base_gllists = "Unknown"
    turret_gllists = "Unknown"

    NO_EXPLOSION_FRAMES = 150
    TARGET_FPS = 50

    def __init__(self, pos, color):
        super().__init__()
        self.pos = pos.copy()
        self.frame_index = 0
        self.color = color

    def _draw(self):
        glPushMatrix()
        glColor(*self.color)
        glTranslate(*self.pos)
        glCallList(Explosion.base_gllists[self.frame_index])
        glPopMatrix()

        glPushMatrix()
        glColor(*self.color)
        glTranslate(*self.pos)
        glCallList(Explosion.turret_gllists[self.frame_index])
        glPopMatrix()

    def update(self):
        # don't play animation too fast
        if self.delta_time() < 1 / self.TARGET_FPS:
            pass

        self._draw()

        self.frame_index += 1
        if self.frame_index >= Explosion.NO_EXPLOSION_FRAMES:
            self.die()


class MineExplosion(Explosion):
    gllists = "Unknown"
    MAX_FRAMES = 50

    def __init__(self, pos, color):
        super().__init__(self, pos, color)

    def draw(self):
        glPushMatrix()
        glColor(*self.color)
        glTranslate(*self.pos)
        glCallList(MineExplosion.gllists[self.frame_index])
        glPopMatrix()


class Shell(bbutils.Shape):
    # how many hits does this weapon deal to a Tank upon contact?
    DAMAGE = 1

    SPEED = 100.0  # m/s

    START_DISTANCE = 10.2  # m, I guess?
    HILL_TIME = 3  # s

    # the shell "explosion" is the still image shown when a shell hits a hill
    explosion_gllist = "Unknown"

    COLOR = (0.7, 0.7, 0.7)
    EXPLO_COLOR = (1.0, 0.635, 0.102)

    SOUND = pygame.mixer.Sound("../data/sound/shell.wav")

    def __init__(self, pos, out, angle, name, in_id=None):
        super().__init__()

        # self._clock is initialized in Shape.__init__
        self.spawn_time = self.clock

        if Shell.gllist == "Unknown":
            Shell.gllist = glGenLists(1)
            glNewList(Shell.gllist, GL_COMPILE)
            exec_raw("../data/models/shell.raw")
            glEndList()
        if Shell.explosion_gllist == "Unknown":
            Shell.explosion_gllist = glGenLists(1)
            glNewList(Shell.explosion_gllist, GL_COMPILE)
            exec_raw("../data/models/explosions/shell_explosion.raw")
            glEndList()

        Shell.SOUND.play()

        self.pos = np.array(pos)
        # raise the shell to make it appear like it's exiting the turret
        # TODO: make a constant for this magic number
        self.pos[1] += 4.1
        self.out = np.array(out)
        self.angle = angle

        # special id, (hopefully) unique to each shell
        if not in_id:
            in_id = id(self)
        self.id = in_id

        # who shot the shell
        self.name = name

        # None until the shell hits a hill; time.time() thereafter
        self.hill_time = None

    def update(self):
        delta = self.delta_time()

        # self.clock is inherited from Shape, and after calling delta_time, will
        # have a value equivalent to time.time()
        if (
            self.hill_time is not None
            and self.clock - self.hill_time >= Shell.HILL_TIME
        ):
            self.die()
            return

        glPushMatrix()
        if not self.hit_hill:
            glColor(*Shell.COLOR)
        else:
            glColor(*Shell.EXPLO_COLOR)
        glTranslate(*self.pos)
        # TODO: modify the Shell model in Blender so this rotate isn't necessary
        glRotate(self.angle, 0.0, 1.0, 0.0)
        if self.hit_hill:
            glCallList(Shell.explosion_gllist)
        else:
            glCallList(Shell.gllist)
        glPopMatrix()

    def hill(self):
        self.hill_time = time.time()


class Mine(bbutils.Shape):
    # time interval between beep noises
    BEEP_INTERVAL = 1  # s
    LIFETIME = 6  # s
    # TODO: move this constant to Tank
    RELOAD = 2  # s

    DAMAGE = 2

    BEEP_SOUND = pygame.mixer.Sound("../data/sound/mine.wav")
    EXPLODE_SOUND = pygame.mixer.Sound("../data/sound/mine_explode.wav")

    def __init__(self, name, pos, color, in_id=None):
        super().__init__()
        self.last_beep_time = self.clock
        self.spawn_time = self.clock

        # gllist is inherited from the bbutils.Shape class
        if self.gllist == "Unknown":
            self.gllist = glGenLists(1)
            glNewList(self.gllist, GL_COMPILE)
            exec_raw("../data/models/mine.raw")
            glEndList()

        self.name = name
        self.pos = np.array(pos)
        self.color = color

        if not in_id:
            in_id = id(self)
        self.id = in_id

    def update(self):
        global allshapes

        # calling this instead of delta_time allows saving a subtraction operation
        self.clock = time.time()

        glPushMatrix()
        glColor(*self.color)
        glTranslate(*self.pos)
        glCallList(Mine.gllist)
        glPopMatrix()

        if self.clock - self.spawn_time >= self.LIFETIME:
            self.die()

            # make a mine explosion
            allshapes.append(MineExplosion(self.pos, self.color))
            return  # so the beep sound can't play

        # make a beep sound periodically
        if self.clock - self.last_beep_time >= self.BEEP_INTERVAL:
            Mine.BEEP_SOUND.play()
            self.last_beep_time = self.clock

    def die(self):
        super().die()
        Mine.EXPLODE_SOUND.play()


class Tank(bbutils.Shape):
    # The tank model is composed of two models: the turret and the base. This is so that
    # the turret can spin independently of the base. B stands for base, T stands for
    # turret.

    # how fast the turret rotates after the player presses "t"
    SNAP_SPEED = 60.0  # deg / s

    # TODO: change units to degrees per second
    BROTATE = 3
    TROTATE = 2

    # the range in which "s" stops the tank
    SNAP_STOP = 0.13  # m/s

    # Speeds
    # 1 OGL unit = 1.74 meter
    # real M1 Abrams acceleration: 2.22
    ACC = 2.0  # m/s**2
    # real M1 Abrams max speed: 35.0
    MAX_SPEED = 10.0  # m/s
    MIN_SPEED = -4.0  # m/s

    RELOAD_TIME = 10  # s
    # how many shell hits before dead?
    # TODO: rename this since a single mine hit does two damage
    HITS_TO_DIE = 5

    blist = "Unknown"
    tlist = "Unknown"

    def __init__(self, pos, out, name, color):
        super().__init__()

        if Tank.blist == "Unknown":
            Tank.blist = glGenLists(1)
            glNewList(Tank.blist, GL_COMPILE)
            exec_raw("../data/models/base.raw")
            glEndList()
        if Tank.tlist == "Unknown":
            Tank.tlist = glGenLists(1)
            glNewList(Tank.tlist, GL_COMPILE)
            exec_raw("../data/models/turret.raw")
            glEndList()

        self.pos = np.array(pos)  # position of the tank
        self.tout = np.array(out)  # which way the turret's facing
        self.bout = np.array(out)  # which way the base is facing

        # snapping back: turret turns to meet base
        # turning back: base turns to meet turret
        # these variables are true if either t or ctrl t have been pressed
        # I believe they can both be true simulatneously
        self.snapping_back = False
        self.turning_back = False

        self.speed = 0.0  # m / s, I hope
        self.bangle = 0.0
        self.tangle = 0.0

        self.ip_bangle = 0
        self.ip_tangle = 0

        self.color = color
        self.name = name
        self.hits_left = Tank.HITS_TO_DIE  # how many more hits before dead?

    def update(self):
        delta = self.delta_time()

        self.routine(delta, self.ip_bangle, self.ip_tangle)

        # TODO: check if the below comment is still true
        # repeated code from Player class, consider combining this in a single method
        self.ip_bangle, self.ip_tangle = self.check_keypresses(self.keys)

        # make sure the angles don't get too high, this helps the turret animation
        self.tangle %= 360.0
        self.bangle %= 360.0

        if self.hits_left <= 0:
            self.die()

    def snap_logic(self, target_angle, approaching_angle, incr):
        """
        Perform calculations for the snapping and turning back animations.

        Returns the increment to be added to the approaching angle (which may be 0)
        and a boolean indicating whether the animation has finished.

        incr should be delta times either Tank.SNAP_SPEED or Tank.BROTATE.
        """
        diff = approaching_angle - target_angle
        # once within a certain threshold of the correct angle, stop snapping back
        if abs(diff) <= incr:
            return diff, True

        if approaching_angle < target_angle:
            return incr, False
        return -incr, False

    def routine(self, delta, ip_bangle=0.0, ip_tangle=0.0):
        if self.snapping_back and ip_tangle == 0.0:
            ip_tangle, finished = self.snap_logic(
                self.bangle, self.tangle, delta * Tank.SNAP_SPEED
            )
            if finished:
                self.snapping_back = False
        if self.turning_back and ip_bangle == 0.0:
            ip_bangle, finished = self.snap_logic(
                self.tangle, self.bangle, delta * Tank.BROTATE
            )
            if finished:
                self.turning_back = False

        if ip_tangle:
            self.tangle += ip_tangle
            self.tout = bbutils.yaw(ip_tangle, self.tout, constants.UP, self.tright)
        if ip_bangle:
            self.bangle += ip_bangle
            self.bout = bbutils.yaw(ip_bangle, self.bout, constants.UP, self.bright)

        # range(len()) may be old-timey, but it's more readable than packing lots of
        # min()s and max()s into list comprehension, and enumerate() is unnecessary
        for i in range(len(self.pos)):
            if self.pos[i] > Ground.HW:
                self.pos[i] = Ground.HW
            if self.pos[i] < -Ground.HW:
                self.pos[i] = -Ground.HW

        for angle, gllist in zip((self.bangle, self.tangle), (self.blist, self.tlist)):
            glPushMatrix()
            glColor(*self.color)
            glTranslate(*self.pos)
            glRotate(angle, 0.0, 1.0, 0.0)
            glCallList(gllist)
            glPopMatrix()

        # move the tank, according to the speed
        self.pos += self.bout * self.speed * delta

    def check_keypresses(self, keys):
        ip_bangle = 0.0
        ip_tangle = 0.0

        if self.turning_back:
            # freeze for now
            return (ip_bangle, ip_tangle)

        shift = keys[K_LSHIFT] or keys[K_RSHIFT]
        ctrl = keys[K_LCTRL] or keys[K_RCTRL]

        if keys[pygame.K_LEFT]:
            if shift:
                ip_tangle = Tank.TROTATE
            elif ctrl:
                ip_bangle = Tank.BROTATE
            else:
                # self.tangle += Tank.BROTATE
                ip_tangle = Tank.BROTATE
                # self.bangle += Tank.BROTATE
                ip_bangle = Tank.BROTATE
        elif keys[pygame.K_RIGHT]:
            if shift:
                # self.tangle -= Tank.TROTATE
                ip_tangle = -Tank.TROTATE
            elif ctrl:
                ip_bangle = -Tank.BROTATE
            else:
                # self.tangle -= Tank.BROTATE
                ip_tangle = -Tank.BROTATE
                # self.bangle -= Tank.BROTATE
                ip_bangle = -Tank.BROTATE
        if keys[pygame.K_UP]:
            # speed up
            self.speed = max(self.speed + Tank.ACC * delta, Tank.MAX_SPEED)
        if keys[pygame.K_DOWN]:
            # slow down
            self.speed = max(self.speed - Tank.ACC * delta, Tank.MIN_SPEED)
        if keys[pygame.K_t]:
            if ctrl:
                self.turning_back = True
            else:
                self.snapping_back = True
        if keys[pygame.K_s] and abs(self.speed) <= Tank.SNAP_STOP:
            self.speed = 0.0

        return (ip_bangle, ip_tangle)

    def recv_data(self, data):
        self.pos = np.array(data["pos"])
        self.bout = np.array(data["bout"])
        self.tout = np.array(data["tout"])
        self.speed = data["speed"]
        self.name = data["name"]
        self.bangle = data["bangle"]
        self.tangle = data["tangle"]
        self.keys = data["keys"]

    def recv_hit(self, weapon="tank", player=False):
        """
        Decrement tank health meter and print obituary as necessary.

        weapon should be either "tank" or "mine".

        If set to True, player will change the obituary.
        """

        # TODO: replace "weapon" arg with a damage arg
        if weapon == "tank":
            increment = Shell.DAMAGE
        if weapon == "mine":
            increment = Mine.DAMAGE

        self.hits_left -= increment
        if self.hits_left == 0:
            if player and not won:
                self.die()
                print("You died!")
            else:
                self.die()
                print(f"{self.name} died.")

    # vector properties

    # TODO: if these vectors are actually left instead of right, rename them
    @property
    def tright(self):
        return bbutils.normalize(np.cross(constants.UP, self.tout))

    @property
    def bright(self):
        return bbutils.normalize(np.cross(constants.UP, self.bout))


class Player(Tank):
    def __init__(self, pos):
        # TODO: Upon startup, have the server providd players with an arbitrary bangle
        super().__init__(
            pos=pos, out=np.array((0.0, 0.0, 1.0)), name="Gandalf", color=(0, 1, 0)
        )

        # the value of pygame.key.get_pressed last frame
        self.prev_keymap = pygame.key.get_pressed()

    def update(self):
        # make sure the angles don't get too high, this helps the turret animation
        self.tangle %= 360.0
        self.bangle %= 360.0

        # keytable:
        # to do this            press this
        # --------------------------------
        # speed up              up arrow
        # slow down             down arrow
        # turn tank left        left arrow
        # turn tank right       right arrow
        # turn turret left      shift+left arrow
        # turn turret right     shift+right arrow
        # look up               shift+up arrow
        # look down             shift+down arrow
        # align turret with baset
        # stop                  s

        keys = pygame.key.get_pressed()

        ip_bangle, ip_tangle = self.check_keypresses(keys)
        # routine inherited from Tank class
        self.routine(ip_bangle, ip_tangle)

        # check if the keypress state has changed since last time
        if keys != self.prev_keymap:
            # TODO: tell the client to send the keymap to the server
            pass

        # remember the old keymap state
        self.prev_keymap = keys


# TODO: make an abstract class containing shared code from Tank, Player, and Spectator
class Spectator(bbutils.Shape):
    HEIGHT = 20.0  # m
    SPEED = 10.0  # m/s
    FAST_SPEED = 30.0  # m/s

    # speed of rising animation after death
    RISE_SPEED = 0.2  # m/s

    # how fast to turn when left or right arrow keys are pressed
    ROTATE_SPEED = 2  # deg / s

    def __init__(self, pos, out, right, angle):
        super().__init__()

        self.pos = np.array(pos)
        self.out = out

    def update(self):
        delta = super().delta_time()

        # "rise" animation
        if self.pos[1] < self.HEIGHT:
            self.pos[1] = min(self.pos[1] + (self.RISE_SPEED * delta), self.HEIGHT)

        keys = pygame.key.get_pressed()

        ip_r = 0.0
        if keys[pygame.K_LEFT]:
            ip_r = self.ROTATE_SPEED * delta
        elif keys[pygame.K_RIGHT]:
            ip_r = -self.ROTATE_SPEED * delta
        if ip_r:
            self.out = bbutils.yaw(ip_r, self.out, constants.UP, self.right)

        speed = 0
        shift = keys[K_LSHIFT] or keys[K_RSHIFT]
        if keys[pygame.K_UP]:
            speed = 1
        elif keys[pygame.K_DOWN]:
            speed = -1
        if shift:
            speed *= self.FAST_SPEED
        else:
            speed *= self.SPEED
        self.pos += self.out * speed * delta

    @property
    def right(self):
        return bbutils.normalize(np.cross(constants.UP, self.out))


class VictoryBanner:
    """A cute little victory banner when you win."""

    # length of the zoom animation
    ZOOM_DURATION = 0.3  # s
    # scale of the banner at the beginning of the animation
    ZOOM_SCALE = 20.0  # at the beginning
    # final scale factor at the end of the animation
    FINAL_SCALE = 1.0
    DIFF_SCALE = FINAL_SCALE - ZOOM_SCALE

    def __init__(self, screen):
        # generate texture
        glEnable(GL_TEXTURE_2D)
        self.texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.texture)
        tex_image = pygame.image.load("../data/images/victory.png")
        self.width = tex_image.get_width()
        self.height = tex_image.get_height()
        glTexImage2D(
            GL_TEXTURE_2D,
            0,
            GL_RGBA,
            self.width,
            self.height,
            0,
            GL_RGBA,
            GL_UNSIGNED_BYTE,
            pygame.image.tostring(tex_image, "RGBX", 1),
        )
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)

        self.spawn_time = time.time()

    def draw(self):
        """Draw the text overlay. I stole 99% of this class from Astrocrash."""
        if current_time := time.time() < self.spawn_time + self.ZOOM_DURATION:
            zoomscale = max(
                self.FINAL_SCALE,
                self.DIFF_SCALE
                * ((current_time - self.spawn_time) / self.ZOOM_DURATION),
            )
        else:
            zoomscale = 1

        glPushMatrix()
        glLoadIdentity()

        half_width = int(SCR[0] / 2)
        half_height = int(SCR[1] / 2)

        half_texwidth = int(self.width / 2) * zoomscale
        half_texheight = int(self.height / 2) * zoomscale

        pts = window2view(
            [
                ((half_width - half_texwidth), (half_height - half_texheight)),
                ((half_width - half_texwidth), (half_height + half_texheight)),
                ((half_width + half_texwidth), (half_height + half_texheight)),
                ((half_width + half_texwidth), (half_height - half_texheight)),
            ]
        )

        # turn on alpha blending
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_BLEND)

        # draw the model
        glColor(1.0, 1.0, 1.0)  # ?
        glDisable(GL_LIGHTING)
        glBindTexture(GL_TEXTURE_2D, self.texture)
        glBegin(GL_QUADS)
        for pt, coord in zip(pts, ((0.0, 0.0), (0.0, 1.0), (1.0, 1.0), (1.0, 0.0))):
            glTexCoord2f(*coord)
            glVertex(pt)
        glEnd()
        glEnable(GL_LIGHTING)

        glDisable(GL_BLEND)
        glPopMatrix()


class LifeBar:
    """Overlay to show how much armor you have left."""

    IMGS = [
        pygame.image.load("../data/images/AAGH5.png"),
        pygame.image.load("../data/images/AAGH4.png"),
        pygame.image.load("../data/images/AAGH3.png"),
        pygame.image.load("../data/images/AAGH2.png"),
        pygame.image.load("../data/images/AAGH1.png"),
        pygame.image.load("../data/images/blank.png"),
    ]
    MARGIN = 50
    UNIT = 200

    def __init__(self, screen):
        self.index = 0

        self.newimg_stuff(screen)

    def draw(self):
        """Draw the LifeBar overlay."""

        glPushMatrix()
        glLoadIdentity()
        glCallList(self.gllist)
        glPopMatrix()

    def change_image(self, screen, weapon="tank"):
        if weapon == "tank":
            increment = 1
        elif weapon == "mine":
            increment = Mine.DAMAGE
        else:
            print("HEAVEN HELP US! I'VE GONE INSANE AT LAST!")

        # TODO: make this method receive a "health" argument instead of independently
        # calculating health values
        self.index += increment

        self.newimg_stuff(screen)

    # TODO: find a better name for this method
    def newimg_stuff(self, screen):
        # generate texture
        glEnable(GL_TEXTURE_2D)
        self.texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.texture)
        try:
            self.current_image = LifeBar.IMGS[self.index]
        except IndexError:
            pass
        glTexImage2D(
            GL_TEXTURE_2D,
            0,
            GL_RGBA,
            self.current_image.get_width(),
            self.current_image.get_height(),
            0,
            GL_RGBA,
            GL_UNSIGNED_BYTE,
            pygame.image.tostring(self.current_image, "RGBX", 1),
        )
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)

        # draw the texture into a display list
        pts = [
            (
                screen[0] - LifeBar.MARGIN - LifeBar.UNIT,
                screen[1] - LifeBar.MARGIN - LifeBar.UNIT,
            ),
            (screen[0] - LifeBar.MARGIN - LifeBar.UNIT, screen[1] - LifeBar.MARGIN),
            (screen[0] - LifeBar.MARGIN, screen[1] - LifeBar.MARGIN),
            (screen[0] - LifeBar.MARGIN, screen[1] - LifeBar.MARGIN - LifeBar.UNIT),
        ]
        glPushMatrix()
        glLoadIdentity()
        pts = window2view(pts)

        self.gllist = glGenLists(1)
        glNewList(self.gllist, GL_COMPILE)

        # turn on alpha blending
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_BLEND)

        # draw the model
        glColor(1.0, 1.0, 1.0)  # ?
        glDisable(GL_LIGHTING)
        glBindTexture(GL_TEXTURE_2D, self.texture)
        glBegin(GL_QUADS)
        glTexCoord2f(0.0, 0.0)
        glVertex(pts[0])
        glTexCoord2f(0.0, 1.0)
        glVertex(pts[1])
        glTexCoord2f(1.0, 1.0)
        glVertex(pts[2])
        glTexCoord2f(1.0, 0.0)
        glVertex(pts[3])
        glEnd()
        glEnable(GL_LIGHTING)

        glDisable(GL_BLEND)
        glEndList()
        glPopMatrix()


class ReloadingBar:
    RISE_DURATION = 0.35  # s
    HEIGHT = 10.0  # px
    COLOR = [0.3, 0.05, 0.0]

    def __init__(self):
        self.width = 0
        self.height = 0

    def fire(self):
        """Call right after the player fires."""

        self.width = SCR[0]
        self.height = 0
        self.spawn_time = time.time()

    def draw(self, reloading):
        """Draw the reloading bar"""
        current_time = time.time()

        # if the player is not currently reloading, do not draw anything
        if current_time > reloading:
            return

        # slide-up animation
        if (
            self.width > 0.0
            and self.height < ReloadingBar.HEIGHT
            and self.width > ReloadingBar.HEIGHT
        ):
            self.height = self.HEIGHT * (
                (time.time() - self.spawn_time) / self.RISE_DURATION
            )

        # slide-down animation
        if self.width <= ReloadingBar.HEIGHT and self.width > 0.0:
            self.height = self.HEIGHT * (
                1 - ((time.time() - self.spawn_time) / self.RISE_DURATION)
            )

        if reloading > 0.0:
            self.width = SCR[0] * ((reloading - current_time) / Tank.RELOAD_TIME)

        # TODO: remove the int(round())s and see if anything breaks
        pts = np.array(
            [
                (0.0, int(round(self.height)), 0.0),
                (self.width, int(round(self.height)), 0.0),
                (self.width, 0, 0.0),
                (0.0, 0, 0.0),
                (0.0, int(round(self.height)), 0.0),
            ]
        )

        glPushMatrix()
        glLoadIdentity()
        glDisable(GL_LIGHTING)
        glColor(*ReloadingBar.COLOR)

        glBegin(GL_POLYGON)
        pts = window2view(pts)
        for point in pts:
            glVertex(point)
        glEnd()

        glEnable(GL_LIGHTING)
        glPopMatrix()


class Game:
    def __init__(self) -> None:
        # uncomment this when networking is reimplemented
        # self.client = Client(self)

        self.players: dict[int, PlayerData] = {}

        # TODO: implement PlayerInputHandler
        # self.input_handler = PlayerInputHandler(self.client)
        # id of the player playing on this computer
        # assigned upon receiving an ID message
        self.player_id = None

    async def initialize(self, ip) -> None:
        """Things that can't go in __init__ because they're coros"""
        # uncomment this when networking is reimplemented
        # await self.client.start(ip)
        pass

    async def assign_name(self) -> None:
        name = await aioconsole.ainput("Enter your name: ")
        # TODO: uncomment this when networknig is reimplemented
        # await self.client.greet(name)

    async def handle_message(self, message: dict, tg: asyncio.TaskGroup) -> None:
        """Handle a JSON-loaded dict network message."""
        print("handle_message called, but is unimplemented")
        pass


async def main(host, no_music):
    global won, SCR, explosion, mines, allshapes, spectating

    print("Welcome to Bang Bang " + constants.VERSION)

    game = Game()
    await game.initialize(host)

    # initialize pygame to display OpenGL
    screen = pygame.display.set_mode(flags=OPENGL | DOUBLEBUF | FULLSCREEN | HWSURFACE)
    SCR = (screen.get_width(), screen.get_height())

    # hide the mouse
    pygame.mouse.set_visible(False)

    # start music ASAP if the user wants it
    if not no_music:
        pygame.mixer.music.load("../data/sound/theme.mp3")
        pygame.mixer.music.play(-1)  # play the theme song on loop

    # set the window title
    pygame.display.set_caption("Bang Bang " + constants.VERSION)

    # initialize glut
    glutInit()

    # enable depth and turn on lights
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_LIGHT0)
    glEnable(GL_LIGHTING)

    # position the sun in an "afternoon" position for best tank lighting
    glLightfv(GL_LIGHT0, GL_POSITION, (Ground.HW * 0.5, 300.0, Ground.HW * 0.5))

    # turn on colors
    glColorMaterial(GL_FRONT, GL_DIFFUSE)
    glEnable(GL_COLOR_MATERIAL)

    # set up the camera lens
    glMatrixMode(GL_PROJECTION)
    gluPerspective(45.0, float(SCR[0]) / float(SCR[1]), 0.1, Ground.DIAGONAL)
    glMatrixMode(GL_MODELVIEW)

    # set up the explosion displaylists
    setup_explosion()

    # NATURE

    # make the sky blue
    glClearColor(0.25, 0.89, 0.92, 1.0)

    # make the ground
    ground = Ground()
    ground.gen_list()

    # TODO: reimplement this
    # hillposes, treeposes = client.get_naturalobjs()
    hillposes = []
    treeposes = []
    hills = [Hill(pos) for pos in hillposes]
    trees = [Tree(pos) for pos in treeposes]

    # Add the tanks
    # TODO: implement this
    tanks = []

    # Make allshapes
    player = Player(np.zeros(3, dtype=float))
    allshapes = [ground, player] + hills + trees + tanks  # get all of the shapes
    drot = np.radians(1.0)
    lifebar = LifeBar(SCR)

    # groups
    shells = []
    playershells = []
    mines = []

    reloadingbar = ReloadingBar()

    # this variable is assigned when this player wins
    victory_banner = None

    # TODO: implement a reloading timer for dropping mines
    # It should probably not be implemented here in the main loop, but that's where
    # this comment is because it used to be implemented here

    # load sounds
    crash = pygame.mixer.Sound("../data/sound/crash.wav")
    # TODO: rename this variable and the wav file to something like "hit_sound"
    explosion = pygame.mixer.Sound("../data/sound/explosion.wav")

    # reloading is the time at which the player can fire again
    reloading = time.time()

    # timestamp of the final frame
    end_time = None

    # the average of this array is used to estimate the FPS
    # it contains the lengths, in seconds, of the past few frames
    fps_history = np.zeros(constants.FPS_HISTORY_LENGTH, dtype=float)
    frame_end_time = time.time()

    while end_time is None or frame_end_time < end_time:
        frame_start_time = frame_end_time

        # listen for input device events
        pygame.event.pump()

        # print FPS to the console when the F key is pressed
        if pygame.key.get_pressed()[pygame.K_f]:
            # np.mean(fps_history) is the average length, in seconds, of the past
            # constants.FPS_HISTORY_LENGTH frames
            print(f"{int(round(1 / np.mean(fps_history)))} FPS")

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
        if spectating:
            pos = spectator.pos
            out = spectator.out
        else:
            pos = player.pos.copy()
            pos[1] = 6.0
            out = player.tout
        at = out + pos

        gluLookAt(*pos, *at, *constants.UP)

        for shape in allshapes:
            shape.update()

        # make bullet on space
        # TODO: add networking to this
        if (
            pygame.key.get_pressed()[pygame.K_SPACE]
            and reloading < time.time()
            and player.alive
            and end_time is None
        ):
            temp_tout = player.tout + (player.bout * player.speed) / Shell.SPEED
            temp_pos = np.array(player.pos) + Shell.START_DISTANCE * np.array(
                player.tout
            )
            shell = Shell(temp_pos, temp_tout, player.tangle, "Gandalf")
            shells.append(shell)
            playershells.append(shell)
            allshapes.append(shell)

            # set reloading bar to full
            reloadingbar.fire()

            reloading = time.time() + Tank.RELOAD_TIME

        # TODO: add networking to this
        if pygame.key.get_pressed()[pygame.K_b] and player.alive and end_time is None:
            mine = Mine(player.name, player.pos, player.color)
            mines.append(mine)
            allshapes.append(mine)
            mine_reload = Mine.RELOAD

            if (not won) and (not spectating):
                # we died, now enter spectate mode.
                spectating = True

                spectator = Spectator(
                    player.pos, player.tout, player.up, player.tright, player.tangle
                )
                allshapes.append(spectator)
            # TODO: simplify this confusing endgame logic
            if (len(tanks) == 1) or won:
                end_time = frame_start_time + 3
                pygame.mixer.music.fadeout(3000)

        # check for collisions
        for hill in hills:
            # tank vs. hill
            if collide_hill(player, hill, False, player.bout):
                # Calculate a vector away from the hill. Does that make sense? :P
                # away = bbutils.normalize(hill.pos - player.pos)
                away = bbutils.normalize(player.pos - hill.pos)

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
                            tank.pos = (20 + COLLISION_SPRINGBACK) * bbutils.normalize(
                                tank.pos - hill.pos
                            ) + hill.pos
                        if collide_hill(player, hill, False, player.bout):
                            player.pos = (
                                20 + COLLISION_SPRINGBACK
                            ) * bbutils.normalize(player.pos - hill.pos) + hill.pos
                for tree in trees:
                    if collide_tank(tree, tank, tank.bout) and not tree.falling.any():
                        tree.fall(bad_tank.bright, 0.5)
                    if collide_tank(tree, player, tank.bout) and not tree.falling.any():
                        tree.fall(bad_tank.bright, 0.5)
                tank.speed = 0.0
                player.speed = 0.0

        for shell in shells:
            for i in range(len(shell.pos)):
                if shell.pos[i] > Ground.HW or shell.pos[i] < -Ground.HW:
                    shell.hill()

        # draw victory banner, if it exists
        # a better way to do this might be to use hasattr(victory_banner, "draw")
        if victory_banner is not None:
            victory_banner.draw()

        # update lifebar
        if player.hits_left > 0:
            lifebar.draw()

        # update reloadingbar
        reloadingbar.draw(reloading)

        pygame.display.flip()

        # discard the oldest frame length and add the newest one
        fps_history = np.roll(fps_history, -1)
        frame_end_time = time.time()
        fps_history[-1] = frame_end_time - frame_start_time
