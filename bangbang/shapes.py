import time

from OpenGL.GL import *
import numpy as np
import pygame

from base_shapes import Shape
from client import PlayerData
import utils_3d

pygame.mixer.init()


class Explosion(Shape):
    NO_FRAMES = 150
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
        if self.frame_index >= self.NO_FRAMES:
            self.die()


class Ground(Shape):
    """A plane that serves as the ground."""

    COLOR = (0.1, 0.3, 0.0)
    POS = (0, 0, 0)

    def __init__(self, ground_hw):
        super().__init__()

        # generate a gllist
        Ground.gllist = glGenLists(1)
        glNewList(Ground.gllist, GL_COMPILE)
        glBegin(GL_POLYGON)
        glNormal(0.0, 1.0, 0.0)
        glVertex(self.POS[0] - ground_hw, self.POS[1], self.POS[2] - ground_hw)
        glNormal(0.0, 1.0, 0.0)
        glVertex(self.POS[0] + ground_hw, self.POS[1], self.POS[2] - ground_hw)
        glNormal(0.0, 1.0, 0.0)
        glVertex(self.POS[0] + ground_hw, self.POS[1], self.POS[2] + ground_hw)
        glNormal(0.0, 1.0, 0.0)
        glVertex(self.POS[0] - ground_hw, self.POS[1], self.POS[2] + ground_hw)
        glNormal(0.0, 1.0, 0.0)
        # the last point must close the square
        glVertex(self.POS[0] - ground_hw, self.POS[1], self.POS[2] - ground_hw)
        glEnd()
        glEndList()

    def update(self):
        glPushMatrix()
        glColor(*Ground.COLOR)
        glTranslate(*self.POS)
        glCallList(Ground.gllist)
        glPopMatrix()


class Hill(Shape):
    def __init__(self, pos):
        super().__init__()
        if Hill.gllist == "Unknown":
            Hill.gllist = glGenLists(1)
            glNewList(Hill.gllist, GL_COMPILE)
            utils_3d.exec_raw("../data/models/hill2.raw")
            glEndList()

        self.pos = np.array(pos)

    def update(self):
        glPushMatrix()
        glColor(0.1, 0.3, 0.0)
        glTranslate(*self.pos)
        glCallList(Hill.gllist)
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

    def __init__(self, player_data: PlayerData, screen: tuple[int]):
        self.player_data = player_data
        self.screen = screen
        self.newimg_stuff()

    def draw(self):
        """Draw the LifeBar overlay."""

        glPushMatrix()
        glLoadIdentity()
        glCallList(self.gllist)
        glPopMatrix()

    # TODO: find a better name for this method
    def newimg_stuff(self):
        # generate texture
        glEnable(GL_TEXTURE_2D)
        self.texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.texture)
        try:
            self.current_image = LifeBar.IMGS[self.player_data.hits_left]
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
                self.screen[0] - LifeBar.MARGIN - LifeBar.UNIT,
                self.screen[1] - LifeBar.MARGIN - LifeBar.UNIT,
            ),
            (
                self.screen[0] - LifeBar.MARGIN - LifeBar.UNIT,
                self.screen[1] - LifeBar.MARGIN,
            ),
            (self.screen[0] - LifeBar.MARGIN, self.screen[1] - LifeBar.MARGIN),
            (
                self.screen[0] - LifeBar.MARGIN,
                self.screen[1] - LifeBar.MARGIN - LifeBar.UNIT,
            ),
        ]
        glPushMatrix()
        glLoadIdentity()
        pts = utils_3d.window2view(pts)

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


class Mine(Shape):
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

        if self.gllist == "Unknown":
            self.gllist = glGenLists(1)
            glNewList(self.gllist, GL_COMPILE)
            utils_3d.exec_raw("../data/models/mine.raw")
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


class MineExplosion(Explosion):
    NO_FRAMES = 50

    def __init__(self, pos, color):
        super().__init__(self, pos, color)

    def draw(self):
        glPushMatrix()
        glColor(*self.color)
        glTranslate(*self.pos)
        glCallList(MineExplosion.gllists[self.frame_index])
        glPopMatrix()


# NOTE TO SELF: if this isn't appearing, make sure it is the last shape drawn
class ReloadingBar:
    RISE_DURATION = 0.35  # s
    HEIGHT = 10.0  # px
    COLOR = [0.3, 0.05, 0.0]

    def __init__(self, screen_width):
        self.width = 0
        self.height = 0
        self.screen_width = screen_width

    def fire(self):
        """Call right after the player fires."""

        self.width = self.screen_width
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
            self.width = self.screen_width * (
                (reloading - current_time) / Tank.RELOAD_TIME
            )

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
        pts = utils_3d.window2view(pts)
        for point in pts:
            glVertex(point)
        glEnd()

        glEnable(GL_LIGHTING)
        glPopMatrix()


class Shell(Shape):
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
            utils_3d.exec_raw("../data/models/shell.raw")
            glEndList()
        if Shell.explosion_gllist == "Unknown":
            Shell.explosion_gllist = glGenLists(1)
            glNewList(Shell.explosion_gllist, GL_COMPILE)
            utils_3d.exec_raw("../data/models/explosions/shell_explosion.raw")
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


# TODO: make an abstract class containing shared code from Tank, Player, and Spectator
class Spectator(Shape):
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
            self.out = utils_3d.yaw(ip_r, self.out, self.right)

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
        return utils_3d.normalize(np.cross(constants.UP, self.out))


class Tank(Shape):
    # The tank model is composed of two models: the turret and the base. This is so that
    # the turret can spin independently of the base. B stands for base, T stands for
    # turret.

    blist = "Unknown"
    tlist = "Unknown"

    def __init__(self, game: "game.Game", client_id: int):
        super().__init__()

        if Tank.blist == "Unknown":
            Tank.blist = glGenLists(1)
            glNewList(Tank.blist, GL_COMPILE)
            utils_3d.exec_raw("../data/models/base.raw")
            glEndList()
        if Tank.tlist == "Unknown":
            Tank.tlist = glGenLists(1)
            glNewList(Tank.tlist, GL_COMPILE)
            utils_3d.exec_raw("../data/models/turret.raw")
            glEndList()

        self.game = game
        self.client_id = client_id

    def update(self):
        for angle, gllist in (
            (self.state.bangle, self.blist),
            (self.state.tangle, self.tlist),
        ):
            glPushMatrix()
            glColor(*self.state.color)
            glTranslate(*self.state.pos)
            glRotate(angle, *constants.UP)
            glCallList(gllist)
            glPopMatrix()

    @property
    def state(self):
        return self.game.players[self.client_id]


class Tree(Shape):
    ACC = 30.0  # degrees/s**2
    FALL_SOUND = pygame.mixer.Sound("../data/sound/tree.wav")
    hit_height = 3.0  # where the tank hits the tree

    def __init__(self, pos):
        super().__init__()
        if Tree.gllist == "Unknown":
            Tree.gllist = glGenLists(1)
            glNewList(Tree.gllist, GL_COMPILE)
            utils_3d.exec_raw("../data/models/tree_lowpoly.raw")
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
        self.screen = screen

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

        # TODO: some of these calculations can be moved from draw() to __init__()
        half_width = int(self.screen[0] / 2)
        half_height = int(self.screen[1] / 2)

        half_texwidth = int(self.width / 2) * zoomscale
        half_texheight = int(self.height / 2) * zoomscale

        pts = utils_3d.window2view(
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


def setup_explosion():
    """Set shape gllists from utils_3d.setup_explosion."""
    # TODO: isn't it un-Pythonic to set class-wide variables like this? What's a cleaner alternative?
    (
        Explosion.base_gllists,
        Explosion.turret_gllists,
        MineExplosion.gllists,
    ) = utils_3d.setup_explosion(Explosion.NO_FRAMES, MineExplosion.NO_FRAMES)
