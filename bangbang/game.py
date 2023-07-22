import asyncio
import math
import random
import subprocess
import sys
from time import sleep, time

import numpy as np

import pygame
from pygame.locals import *

from OpenGL.GL import *
from OpenGL.GLU import *
from OpenGL.GLUT import *

sys.path.append("../PodSixNet")
from PodSixNet.Connection import connection, ConnectionListener

from bbutilities import *
from version import __version__

won = False # Did we win?
playgame = True
spectating = False # Are we in spectate mode?

pygame.init() # initialize pygame

COLLISION_SPRINGBACK = 10.0 #10.1 / FPS

def window2view(pts):
    """
    Convert window coordinates to 3D coordinates.
    """
    model = glGetDoublev(GL_MODELVIEW_MATRIX)
    projection = glGetDoublev(GL_PROJECTION_MATRIX)
    viewport = glGetIntegerv(GL_VIEWPORT)

    retval = [gluUnProject(pt[0], pt[1], 0.001, model, projection, viewport) for pt in pts]

    return retval

def exec_raw(full_name):
    """
    Read in a triangular representation of a piece for rendering.
    Used a home-grown format which was much faster than stl or ogl.gz
    reading.
    """

    try:
        rawdata = np.fromfile(full_name, np.float32)
    except IOError:
        print(('Couldn\'t find', full_name))
        sys.exit()

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
    
    if Explosion.base_gllists == "Unknown":

        Explosion.base_gllists = []
        for i in range(Explosion.NO_EXPLOSION_FRAMES):
            if len(str(i + 1)) == 1:
                name = "../data/models/explosions/base_explosion_00000" + str(i + 1) + ".raw"
            elif len(str(i + 1)) == 2:
                name = "../data/models/explosions/base_explosion_0000" + str(i + 1) + ".raw"
            else:
                name = "../data/models/explosions/base_explosion_000" + str(i + 1) + ".raw"
            gllist = glGenLists(1)
            glNewList(gllist, GL_COMPILE)
            exec_raw(name)
            glEndList()

            Explosion.base_gllists.append(gllist)

    if Explosion.turret_gllists == "Unknown":

        Explosion.turret_gllists = []
        for i in range(Explosion.NO_EXPLOSION_FRAMES):
            if len(str(i + 1)) == 1:
                name = "../data/models/explosions/turret_explosion_00000" + str(i + 1) + ".raw"
            elif len(str(i + 1)) == 2:
                name = "../data/models/explosions/turret_explosion_0000" + str(i + 1) + ".raw"
            else:
                name = "../data/models/explosions/turret_explosion_000" + str(i + 1) + ".raw"
            gllist = glGenLists(1)
            glNewList(gllist, GL_COMPILE)
            exec_raw(name)
            glEndList()

            Explosion.turret_gllists.append(gllist)
            
    if MineExplosion.gllists == "Unknown":

        MineExplosion.gllists = []
        if Explosion.NO_EXPLOSION_FRAMES > MineExplosion.MAX_FRAMES:
            number = MineExplosion.MAX_FRAMES
        else:
            number = Explosion.NO_EXPLOSION_FRAMES
        for i in range(number):
            if len(str(i + 1)) == 1:
                name = "../data/models/explosions/mine_explosion_00000" + str(i + 1) + ".raw"
            else:
                name = "../data/models/explosions/mine_explosion_0000" + str(i + 1) + ".raw"
            gllist = glGenLists(1)
            glNewList(gllist, GL_COMPILE)
            exec_raw(name)
            glEndList()

            MineExplosion.gllists.append(gllist)

class Tree(Shape):
    """ A dead tree. Leafless. *sniff* """

    ACC = 30.0 # degrees/s**2
    FALL_SOUND = pygame.mixer.Sound("../data/sound/tree.wav")
    HIT_HEIGHT = 3.0 # Where the tank hits the tree

    def __init__(self, pos):
        if Tree.gllist == "Unknown":
            Tree.gllist = glGenLists(1)
            glNewList(Tree.gllist, GL_COMPILE)
            exec_raw("../data/models/tree_lowpoly.raw")
            glEndList()

        self.pos = np.array(pos)
        self.alive = True
        # Set to 0 array when tree is alive. Set to tank.right
        # when tree is falling
        self.falling = np.array((0.0, 0.0, 0.0))
        self.fall_angle = 0.0
        self.played_sound = False

    def update(self):
        glPushMatrix()
        glColor(0.64, 0.44, 0.17)
        glTranslate(*self.pos)
        if self.falling.any():
            self.speed += (Tree.ACC / FPS)
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
        """ Called when a tank collides with a tree. """

        if speed > 0:
            self.falling = angle
        if speed < 0:
            self.falling = -angle
        self.speed = speed / Tree.HIT_HEIGHT


class Hill(Shape):
    """
    Object to maneuver around.
    """

    def __init__(self, pos):
        if Hill.gllist == "Unknown":
            Hill.gllist = glGenLists(1)
            glNewList(Hill.gllist, GL_COMPILE)
            exec_raw("../data/models/hill2.raw")
            glEndList()

        self.pos = np.array(pos)
        self.alive = True

    def update(self):
        # Hills are immobile, and at the time of the writing of this
        # comment they each have the same orientation. All we have
        # to do is draw it. Sweet.
        glPushMatrix()
        glColor(0.1, 0.3, 0.0)
        glTranslate(*self.pos)
        glCallList(Hill.gllist)
        glPopMatrix()


class Ground(Shape):
    """ A plane that will serve as the ground. """
    
    COLOR = (0.1, 0.3, 0.0)

    HW = 250 # HW for HalfWidth
    WIDTH = HW * 2
    DIAGONAL = math.sqrt( 2 * (WIDTH ** 2)) # Pythagorean Theorum

    def __init__(self):
        self.pos = np.array((0.0, 0.0, 0.0))

        self.alive = True

    def gen_list(self):
        Ground.gllist = glGenLists(1)
        glNewList(Ground.gllist, GL_COMPILE)
        glBegin(GL_POLYGON)
        glNormal(0.0, 1.0, 0.0)
        glVertex(self.pos[0] - Ground.HW,
                 self.pos[1],
                 self.pos[2] - Ground.HW)
        glNormal(0.0, 1.0, 0.0)
        glVertex(self.pos[0] + Ground.HW,
                 self.pos[1],
                 self.pos[2] - Ground.HW)
        glNormal(0.0, 1.0, 0.0)
        glVertex(self.pos[0] + Ground.HW,
                 self.pos[1],
                 self.pos[2] + Ground.HW)
        glNormal(0.0, 1.0, 0.0)
        glVertex(self.pos[0] - Ground.HW,
                 self.pos[1],
                 self.pos[2] + Ground.HW)
        glNormal(0.0, 1.0, 0.0)
        # The last point must close the square
        glVertex(self.pos[0] - Ground.HW,
                 self.pos[1],
                 self.pos[2] - Ground.HW)
        glEnd()
        glEndList()

    def update(self):
        """
        The playing ground will not be infinite.

        In a multiplayer game, that could cause the players to be
        hopelessly lost. The ground will be fix, and I'll set up some
        sort of barrier so that nobody drives off the Earth.
        """

        glPushMatrix()
        glColor(*Ground.COLOR)
        glTranslate(*self.pos)
        glCallList(Ground.gllist)
        glPopMatrix()


class Explosion(object):
    """ An explosion. """

    base_gllists = "Unknown" # so that the first explosion will set up the display lists
    turret_gllists = "Unknown"

    #NO_EXPLOSION_FRAMES = 24
    #NO_EXPLOSION_FRAMES = 100

    def __init__(self, pos, color):

        self.pos = pos.copy()
        self.frame_index = 0
        self.color = color
        self.alive = True
        
    def update(self):
        if Explosion.NO_EXPLOSION_FRAMES != 0:
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

        self.frame_index += 1

        if self.frame_index >= Explosion.NO_EXPLOSION_FRAMES:
            self.alive = False

    def update_fps(self):
        pass
    
    
class MineExplosion(Explosion):
    
    gllists = "Unknown"
    MAX_FRAMES = 50
    
    def __init__(self, pos, color):
        Explosion.__init__(self, pos, color)
        
        self.frames = min(Explosion.NO_EXPLOSION_FRAMES, MineExplosion.MAX_FRAMES)
    
    def update(self):
        
        if Explosion.NO_EXPLOSION_FRAMES != 0:
            glPushMatrix()
            glColor(*self.color)
            glTranslate(*self.pos)
            glCallList(MineExplosion.gllists[self.frame_index])
            glPopMatrix()

        self.frame_index += 1
        if self.frame_index > self.frames: # Subtract one since we start at 0! Then add one back so that the explosion disappears.
            self.frame_index = self.frames

        if self.frame_index >= self.frames:
            self.alive = False


class Shell(Shape):
    """ Here it is. The whole point of the game. """

    SPEED = 100.0 # m/s

    START_DISTANCE = 10.2
    HILL_TIME = 3 * FPS # n seconds

    explosion_gllist = "Unknown" # If a shell hits a hill, show a still image
    
    COLOR = (0.7, 0.7, 0.7)
    EXPLO_COLOR = (1.0, 0.635, 0.102)

    SOUND = pygame.mixer.Sound("../data/sound/shell.wav")

    def __init__(self, pos, out, angle, name, in_id = None):
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

        #self.pos = np.array(pos) + Shell.START_DISTANCE * np.array(out)
        self.pos = np.array(pos)
        self.original_pos = np.array(pos) # DON'T do self.pos here, I think
        # Put the shell a bit higher to make it appear like it's coming
        # out of the turret
        self.pos[1] += 4.1
        self.out = np.array(out)
        self.angle = angle

        # Special ID, (hopefully) unique to each shell
        if not in_id:
            in_id = id(self)
        self.id = in_id

        # Who shot the shell
        self.name = name

        self.hit_hill = False
        self.hill_timer = Shell.HILL_TIME

        # Make noise
        Shell.SOUND.play()

        self.alive = True

    def update(self):

        if self.hit_hill:
            self.hill_timer -= 1
        else:
            self.pos += self.out * (Shell.SPEED / FPS)

        glPushMatrix()
        if not self.hit_hill:
            glColor(*Shell.COLOR)
        else:
            glColor(*Shell.EXPLO_COLOR)
        glTranslate(*self.pos)
        glRotate(self.angle, 0.0, 1.0, 0.0)
        if self.hit_hill:
            glCallList(Shell.explosion_gllist)
            #self.alive = False
            #print "In shell class: " + self.name + "'s shell either went off the world or hit a hill"
        else:
            glCallList(Shell.gllist)
        glPopMatrix()

        if self.hill_timer <= 0:
            #print self.name + "'s shell hill timer out (" + str(FPS) + " fps)"
            self.alive = False

    def hill(self):
        if not self.hit_hill:
            pass
        self.hit_hill = True

    def die(self):
        self.alive = False
        #print "Shell", self.id, "gave up on life"
        
class Mine(Shape):
    """
    A mine. The balancing of this weapon is a WIP.
    
    The mine is placed under the center of the player's tank and deals two hits upon impact. If nothing
    seems to blow it up before five seconds of the mine's life have elapsed, then the mine will automatically
    detonate. This will deal damage if a tank happens to be over it. A player's mine cannot hurt themselves.
    
    The player has an unlimited supply of mines. They can lay them up to every two seconds. As a twist, the
    color of the mine will be the same as the color of the player who dropped it (if I remember to add that. :P)
    
    TBH, all I really intended to make this for is to deal with those super annoying trollers.
    """
    
    LIFETIME = 6 * FPS # in frames.
    
    DAMAGE = 2
    
    BEEP = pygame.mixer.Sound("../data/sound/mine.wav")
    BEEP_TIME = 1 * FPS # one second by default
    
    EXPLODE = pygame.mixer.Sound("../data/sound/mine_explode.wav")
    
    RELOAD = 2 * FPS # two seconds for now
    
    def __init__(self, name, pos, color, in_id = None):
        
        # Mine.gllist is inherited from the Shape class
        if Mine.gllist == "Unknown":
            Mine.gllist = glGenLists(1)
            glNewList(Mine.gllist, GL_COMPILE)
            exec_raw("../data/models/mine.raw")
            glEndList()
            
        self.alive = True

        self.name = name
        self.pos = np.array(pos)
        self.color = color
        
        if not in_id:
            in_id = id(self)
        self.id = in_id
        
        self.beep_timer = 0 # for the annoying beep sound
        
        self.lifetime = Mine.LIFETIME
        
    def update(self):
        
        glPushMatrix()
        glColor(*self.color)
        glTranslate(*self.pos)
        glCallList(Mine.gllist)
        glPopMatrix()
        
        self.lifetime -= 1
        if self.lifetime <= 0:
            self.alive = False
            
            # make a mine explosion
            allshapes.append(MineExplosion(self.pos, self.color))
            return # so the beep sound can't play
        
        # Do the beep
        self.beep_timer -= 1
        if self.beep_timer <= 0:
            Mine.BEEP.play()
            self.beep_timer = Mine.BEEP_TIME


class Tank(object):

    # We are going to have to draw the front part of the player's tank
    # The player will be the dude poking his head out of the hatch and
    # blasting away everything within sight with the main bangbanger

    # The tank model is composed of two models: the turret
    # and the base. This is so that the turret can spin
    # independently of the base. B stands for base, T stands
    # for turret.

    # How much we rotate per frame after the player presses "t"
    SNAP_INCREMENT = 10.0

    BROTATE = int(round(FPS / 20.))
    TROTATE = int(round(FPS / 10.))

    SNAP_STOP = 8.0 # Have to be in this range to stop

    # Speeds
    # 1 OGL unit = 1.74 meter
    # Real M1 Abrams acceleration: 2.22
    ACC = 2.0 # m/s**2
    # Real M1 Abrams max speed: 35.0
    MAX_SPEED = 10.0 # m/s
    MIN_SPEED = -4.0 # m/s

    HITS_TO_DIE = 5 # How many shell hits before dead?

    blist = "Unknown"
    tlist = "Unknown"

    def __init__(self, pos, out, up, name, color = None):
        if Tank.blist == "Unknown":
            Tank.blist = glGenLists(1)
            glNewList(Tank.blist, GL_COMPILE)
            exec_raw("../data/models/base.raw")
            glEndList()

        # Do the same thing for the turret
        if Tank.tlist == "Unknown":
            Tank.tlist = glGenLists(1)
            glNewList(Tank.tlist, GL_COMPILE)
            exec_raw("../data/models/turret.raw")
            glEndList()

        self.pos = np.array(pos) # position of the tank
        #print name + "'s pos:", self.pos
        self.tout = np.array(out) # which way the turret's facing
        self.bout = np.array(out) # which way the base is facing
        self.up = np.array(up) # which way is up
        self.tright = np.cross(up, out) # which way is left
        self.bright = np.cross(up, out)
        
        # Current Keymap lol
        self.keys = (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                     0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                     0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                     0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                     0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                     0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                     0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                     0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                     0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                     0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                     0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                     0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                     0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                     0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                     0)

        self.snapping_back = False # Whether we're playing the "T Animation" or not
        self.turning_back = False # Now the "Ctrl T Animation", lol

        # OpenGL units per frame
        self.speed = 0.0
        self.bangle = 0.0
        self.tangle = 0.0
        
        self.ip_bangle, self.ip_tangle = 0, 0

        if not color:
            self.color = (random.random(), random.random(), random.random())
        else:
            self.color = color
        self.name = name
        self.hits_left = Tank.HITS_TO_DIE # How many more hits before dead?
        self.alive = True

    def update(self):

        self.routine(self.ip_bangle, self.ip_tangle)

        # Repeated code from Player class, consider combining this in a single method
        self.ip_bangle, self.ip_tangle = self.check_keypresses(self.keys)

        # Make sure the angles don't get too high, this helps the turret animation
        self.tangle %= 360.0
        self.bangle %= 360.0

        if self.hits_left <= 0:
            self.alive = False

    def routine(self, ip_bangle = 0, ip_tangle = 0):

        if self.snapping_back:
            dangle = self.bangle - self.tangle
            if dangle > 180.0:
                #dangle = dangle - 360.0
                dangle -= 360.0
            elif dangle < -180.0:
                #dangle = 360.0 + dangle
                dangle += 360.0

            #ip_tangle = Tank.SNAP_INCREMENT * cmp(dangle, 0.0)
            ip_tangle = Tank.SNAP_INCREMENT * ((dangle > 0.0) - (dangle < 0.0))
            self.tangle += ip_tangle

            #print "snapping..."

            if self.tangle <= self.bangle + Tank.SNAP_INCREMENT and self.tangle >= self.bangle - Tank.SNAP_INCREMENT:
                ip_tangle = 0
                self.tangle = self.bangle
                self.tout = self.bout
                self.tright = self.bright
                #print "finished t animation"
                self.snapping_back = False

        if self.turning_back:
            dangle = self.tangle - self.bangle
            if dangle > 180.0:
                dangle -= 360.0
            elif dangle < -180.0:
                dangle += 360.0

            ip_bangle = Tank.BROTATE * ((dangle > 0.0) - (dangle < 0.0))
            self.bangle += ip_bangle

            if self.bangle <= self.tangle + Tank.BROTATE and self.bangle >= self.tangle - Tank.BROTATE:
                ip_bangle = 0
                self.bangle = self.tangle
                self.bout = self.tout
                self.bright = self.tright
                self.turning_back = False

        for i in range(len(self.pos)):
            if self.pos[i] > Ground.HW:
                self.pos[i] = Ground.HW
            if self.pos[i] < -Ground.HW:
                self.pos[i] = -Ground.HW
                
        glPushMatrix()
        glColor(*self.color)
        glTranslate(*self.pos)
        glRotate(self.bangle, 0.0, 1.0, 0.0)
        glCallList(Tank.blist)
        glPopMatrix()

        glPushMatrix()
        glColor(*self.color)
        glTranslate(*self.pos)
        glRotate(self.tangle, 0.0, 1.0, 0.0)
        glCallList(Tank.tlist)
        glPopMatrix()

        # Move the tank, according to the speed
        self.pos += self.bout * self.speed / FPS
        
        # make the angle changes
        self.tangle += ip_tangle
        self.bangle += ip_bangle
        
        if ip_bangle:
            # Adjust bout to match the new angle (if any)
            self.bout, self.bright = self.yaw(ip_bangle, self.bout,
                                              np.array((0.0, 1.0, 0.0)),
                                              self.bright)

        if ip_tangle:
            # Adjust turret to match the new angle
            self.tout, self.tright = self.yaw(ip_tangle, self.tout,
                                              np.array((0.0, 1.0, 0.0)),
                                              self.tright)

    def yaw(self, angle, out, up, right):
        """ Return out and right """

        # up fixed, out/right change
        out = normalize(np.cos(np.radians(angle))*out + np.sin(np.radians(angle))*right)
        right = normalize(np.cross(up, out))

        return (out, right)

    def check_keypresses(self, keys):

        ip_bangle = 0.0
        ip_tangle = 0.0
        
        if self.turning_back:
            # Freeze for now
            return (ip_bangle, ip_tangle)

        shift = keys[K_LSHIFT] or keys[K_RSHIFT]
        ctrl = keys[K_LCTRL] or keys[K_RCTRL]

        if keys[pygame.K_LEFT]:
            if shift:
                ip_tangle = Tank.TROTATE
            elif ctrl:
                ip_bangle = Tank.BROTATE
            else:
                #self.tangle += Tank.BROTATE
                ip_tangle = Tank.BROTATE
                #self.bangle += Tank.BROTATE
                ip_bangle = Tank.BROTATE
        elif keys[pygame.K_RIGHT]:
            if shift:
                #self.tangle -= Tank.TROTATE
                ip_tangle = -Tank.TROTATE
            elif ctrl:
                ip_bangle = -Tank.BROTATE
            else:
                #self.tangle -= Tank.BROTATE
                ip_tangle = -Tank.BROTATE
                #self.bangle -= Tank.BROTATE
                ip_bangle = -Tank.BROTATE
        if keys[pygame.K_UP]:
            # speed up
            self.speed += Tank.ACC / FPS
            if self.speed > Tank.MAX_SPEED:
                self.speed = Tank.MAX_SPEED
        if keys[pygame.K_DOWN]:
            # slow down
            self.speed -= Tank.ACC / FPS
            if self.speed < Player.MIN_SPEED:
                self.speed = Player.MIN_SPEED
        if keys[pygame.K_t]:
            if ctrl:
                self.turning_back = True
            else:
                self.snapping_back = True
            #print self.name, "pressed t!"
        if keys[pygame.K_s] and self.speed >= -Tank.SNAP_STOP * FPS and self.speed <= Tank.SNAP_STOP * FPS:
            self.speed = 0.0

        return (ip_bangle, ip_tangle)

    def recv_data(self, data):
        self.pos = np.array(data["pos"])
        self.bout = np.array(data["bout"])
        self.tout = np.array(data["tout"])
        self.bright = np.array(data["bright"])
        self.speed = data["speed"]
        self.name = data["name"]
        self.bangle = data["bangle"]
        self.tangle = data["tangle"]
        self.keys = data["keys"]

    def recv_hit(self, weapon = "tank"):
        """ Sense that we hit a shell and do what is necessary. """
        
        if weapon == "tank":
            increment = 1
        if weapon == "mine":
            increment = Mine.DAMAGE

        if self.hits_left > 0:
            self.hits_left -= increment

        if self.hits_left <= 0:
            print(self.name, "died.")

    def update_fps(self):
        """ This code is very impolite, update later """

        Tank.BROTATE = int(round(45. / FPS))
        Tank.TROTATE = int(round(90. / FPS))

        Tank.SNAP_STOP = 1.5 / FPS


class Player(Tank):

    def __init__(self, pos, out, up, name, client, color):
        Tank.__init__(self, pos, out, up, name, color)

        self.client = client # Assign the client so we can tell it when to update

        self.prev_keymap = pygame.key.get_pressed() # The value that pygame.key.get_pressed was last frame

    def update(self):
        
        # Keytable:
        # To do this            Press this
        # --------------------------------
        # Speed up              Up Arrow
        # Slow down             Down Arrow
        # Turn tank left        Left Arrow
        # Turn tank right       Right Arrow
        # Turn turret left      Shift+Left Arrow
        # Turn turret right     Shift+Right Arrow
        # Look up               Shift+Up Arrow
        # Look down             Shift+Down Arrow
        # Align turret with baset
        # Stop                  s

        keys = pygame.key.get_pressed()

        # This is really bad code because any time the player is pressing any key (which is the case more than 50% of the time)
        # the network has to send a signal. This might cause a network data jam, especially when the network is not as high end.
        # if keys:
        #     should_update = True

        ip_bangle, ip_tangle = self.check_keypresses(keys)
        
        # Make sure the angles don't get too high, this helps the turret animation
        self.tangle %= 360.0
        self.bangle %= 360.0

        # Routine inherited from Tank class
        self.routine(ip_bangle, ip_tangle)

        # Check if the keypress state has changed since last time
        if keys != self.prev_keymap:
            #print "Keys have changed"
            self.client.send_attributes(keys)

        # Remember the old keymap state
        self.prev_keymap = keys

    def recv_hit(self, weapon = "tank"):

        global playgame

        if weapon == "tank":
            increment = 1
        if weapon == "mine":
            increment = Mine.DAMAGE

        if self.hits_left > 0:
            self.hits_left -= increment

        if self.hits_left <= 0 and not won:
            print("You died!")
            self.alive = False
            playgame = False

    def update_fps(self):
        Tank.update_fps(self)

        Player.SNAP_INCREMENT = 600.0 / FPS
        
        
class Spectator(Shape):
    """
    Keep track of the vars used for spectating and calculate the out vars based on mouse movement.
    """
    
    HEIGHT = 20.0 # OpenGL units
    SPEED = 10.0 # m/s
    FAST_SPEED = 30.0 # m/s
    
    RISE_TIME = 2.0 # seconds
    INCREMENT = HEIGHT / RISE_TIME
    
    ROTATE = int(round(FPS / 25.0))
    UP = int(round(FPS / 50.0))
    
    def __init__(self, pos, out, up, right, angle):
        
        self.pos = np.array(pos)
        self.out = out
        self.up = up
        self.right = right
        self.angle = angle
        self.speed = 0.0
        
        self.alive = True
        self.ip_r = 0.0

    def update(self):
        
        # "Rise" animation
        if self.pos[1] < Spectator.HEIGHT:
            self.pos[1] += Spectator.INCREMENT / FPS
        
        self.angle += self.ip_r

        self.out, self.right = self.yaw(self.ip_r, self.out, self.up, self.right)
        
        # I originally wanted to go with the standard WASD + mouse for spectating mode, but that was too hard
        # and I just wanted to get spectate mode working quickly. So now it's controlled by the arrow keys.
        
        self.ip_r = 0.0
        
        keys = pygame.key.get_pressed()
        shift = keys[K_LSHIFT] or keys[K_RSHIFT]
               
        if keys[pygame.K_LEFT]:
            self.ip_r = Spectator.ROTATE
        if keys[pygame.K_RIGHT]:
            self.ip_r = -Spectator.ROTATE

        #if self.ip_r:
        #    print(self.ip_r)

        if keys[pygame.K_UP]:
            if shift:
                self.speed = Spectator.FAST_SPEED
            else: 
                self.speed = Spectator.SPEED
        elif keys[pygame.K_DOWN]:
            if shift:
                self.speed = -Spectator.FAST_SPEED
            else:
                self.speed = -Spectator.SPEED
        else:
            self.speed = 0.0
            
        self.angle %= 360.0
        
        self.pos += self.out * self.speed / FPS
        
    def yaw(self, angle, out, up, right):
        """ Return out and right """

        # up fixed, out/right change
        out = normalize(np.cos(np.radians(angle))*out + np.sin(np.radians(angle))*right)
        right = normalize(np.cross(up, out))

        return (out, right)

        
class VictoryBanner(object):
    """ A cute little victory banner when you win. """
    
    ZOOM_DURATION = 0.3 * FPS # The length of the zoom animation, in frames
    #ZOOM_INCREMENT = 1.0 / ZOOM_DURATION
    ZOOM_SCALE = 20.0 # at the beginning
    ZOOM_INCREMENT = -1 * ((ZOOM_SCALE - 1.0) / ZOOM_DURATION)
    
    def __init__(self, screen):
        # Generate Texture
        glEnable(GL_TEXTURE_2D)
        self.texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.texture)
        tex_image = pygame.image.load("../data/images/victory.png")
        self.width = tex_image.get_width()
        self.height = tex_image.get_height()
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA,
                     self.width, self.height,
                     0, GL_RGBA, GL_UNSIGNED_BYTE,
                     pygame.image.tostring(tex_image, "RGBX", 1))
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        
        #self.zoomscale = 0.0 # for the zoom animation
        self.zoomscale = VictoryBanner.ZOOM_SCALE
        
    def draw(self):
        """ Draw the text overlay. I stole 99% of this class from Astrocrash."""

        glPushMatrix()
        glLoadIdentity()
        #glCallList(self.gllist)
        
        half_width = int(SCR[0] / 2)
        half_height = int(SCR[1] / 2)
        
        half_texwidth = int(self.width / 2) * self.zoomscale
        half_texheight = int(self.height / 2) * self.zoomscale
        
        pts = [((half_width - half_texwidth), (half_height - half_texheight)),
               ((half_width - half_texwidth), (half_height + half_texheight)),
               ((half_width + half_texwidth), (half_height + half_texheight)),
               ((half_width + half_texwidth), (half_height - half_texheight))]
               
        pts = window2view(pts)
        
        self.zoomscale += VictoryBanner.ZOOM_INCREMENT
        #if self.zoomscale > 1.0:
        if self.zoomscale < 1.0:
            self.zoomscale = 1.0
        
        # Turn on alpha blending
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_BLEND)

        # Draw the model
        glColor(1.0, 1.0, 1.0) # ?
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

        # Turn off alpha blending
        glDisable(GL_BLEND)

        glPopMatrix()


class LifeBar(object):
    """ Overlay to show how much armor you have left. """

    LIVES = Tank.HITS_TO_DIE
    IMGS = [pygame.image.load("../data/images/AAGH5.png"),
            pygame.image.load("../data/images/AAGH4.png"),
            pygame.image.load("../data/images/AAGH3.png"),
            pygame.image.load("../data/images/AAGH2.png"),
            pygame.image.load("../data/images/AAGH1.png"),
            pygame.image.load("../data/images/blank.png")]
    MARGIN = 50
    UNIT = 200

    def __init__(self, screen):
        self.index = 0

        self.newimg_stuff(screen)

    def draw(self):
        """ Draw the LifeBar overlay. """

        glPushMatrix()
        glLoadIdentity()
        glCallList(self.gllist)
        glPopMatrix()

    def change_image(self, screen, weapon = "tank"):

        if weapon == "tank":
            increment = 1
        elif weapon == "mine":
            increment = Mine.DAMAGE
        else:
            print("HEAVEN HELP US! I'VE GONE INSANE AT LAST!")

        self.index += increment

        self.newimg_stuff(screen)

    def newimg_stuff(self, screen):

        # Generate Texture
        glEnable(GL_TEXTURE_2D)
        self.texture = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, self.texture)
        try:
            self.current_image = LifeBar.IMGS[self.index]
        except(IndexError):
            pass
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA,
                     self.current_image.get_width(),
                     self.current_image.get_height(),
                     0, GL_RGBA, GL_UNSIGNED_BYTE,
                     pygame.image.tostring(self.current_image, "RGBX", 1))
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameterf(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)

        # Draw the texture into a display list
        pts = [(screen[0] - LifeBar.MARGIN - LifeBar.UNIT, (screen[1] - LifeBar.MARGIN - LifeBar.UNIT)),
               (screen[0] - LifeBar.MARGIN - LifeBar.UNIT, (screen[1] - LifeBar.MARGIN)),
               (screen[0] - LifeBar.MARGIN, screen[1] - LifeBar.MARGIN),
               (screen[0] - LifeBar.MARGIN, (screen[1] - LifeBar.MARGIN - LifeBar.UNIT))]
        glPushMatrix()
        glLoadIdentity()
        pts = window2view(pts)

        self.gllist = glGenLists(1)
        glNewList(self.gllist, GL_COMPILE)

        # Turn on alpha blending
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_BLEND)

        # Draw the model
        glColor(1.0, 1.0, 1.0) # ?
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

        # Turn off alpha blending
        glDisable(GL_BLEND)

        glEndList()
        glPopMatrix()


class ReloadingBar(object):

    HEIGHT = 10.0
    COLOR = [0.3, 0.05, 0.0]

    def __init__(self):

        self.width = 0
        self.height = 0

    def fire(self):
        """ Call right after the player fires. """

        self.width = SCR[0]
        self.height = 0

    def draw(self, reloading):
        """ Draw the reloading bar """

        # Slide-up animation
        if (self.width > 0.0) and (self.height < ReloadingBar.HEIGHT) \
           and (self.width > ReloadingBar.HEIGHT):
            self.height += (30. / FPS)

        # Slide-down animation
        if self.width <= ReloadingBar.HEIGHT and self.width > 0.0:
            self.height -= (30. / FPS)

        if reloading > 0.0:
            self.width = (reloading * SCR[0]) / RELOAD_TIME
        else:
            # Don't waste processing power
            return

        pts = np.array([(0.0, int(round(self.height)), 0.0),
                        (self.width, int(round(self.height)), 0.0),
                        (self.width, 0, 0.0),
                        (0.0, 0, 0.0),
                        (0.0, int(round(self.height)), 0.0)
                        ])

        glPushMatrix()
        glLoadIdentity()
        pts = window2view(pts)

        glDisable(GL_LIGHTING)
        glColor(*ReloadingBar.COLOR)

        glBegin(GL_POLYGON)
        for point in pts:
            glVertex(point)
        glEnd()

        glEnable(GL_LIGHTING)
        glPopMatrix()


class DummyPlayer(object):
    def __init__(self, pos = (0.0, 0.0, 0.0), out = (0.0, 0.0, 1.0), up = None, name = None, color = None):
        self.pos = np.array(pos)
        self.bout = np.array(out)
        self.tout = np.array(out)
        self.bright = np.array((0.0, 0.0, 0.0))
        self.speed = (Tank.MAX_SPEED + Tank.MIN_SPEED) / 2.
        self.color = color
        #print "Dummy's color is", color

        self.tangle = 0.0
        self.bangle = 0.0

        self.hits_left = Tank.HITS_TO_DIE


async def main(host, port, fps, explo_frames, no_music):

    global should_update, to_updates, make_shell, \
           playgame, dead_tank, won, FPS, \
           SCR, lifebar, explosion, RELOAD_TIME, deadshell_id, mines, \
           allshapes, deadmine_id, spectating

    print("Welcome to Bang Bang " + __version__)

    FPS = fps

    # Create a client class
    # The client will wait until all other players are ready
    client = Client(host, port)

    # Initialize pygame to display OpenGL
    #pygame.init()
    screen = pygame.display.set_mode((0, 0), OPENGL|DOUBLEBUF|FULLSCREEN|HWSURFACE)
    SCR = [screen.get_width(), screen.get_height()]
    pygame.mouse.set_visible(False) # hide the mouse
    
    # Start music ASAP. Only if the user wants it.
    if not no_music:
        pygame.mixer.music.load("../data/sound/theme.mp3")
        pygame.mixer.music.play(-1) # play the theme song on loop

    # Set the window title
    title = client.name + " | Bang Bang Tanks " + __version__
    #if high_graphics:
    #    print "Long story short, I've been having a couple issues with HG mode."
    #    print "I disabled it for now. HAHAHAHA"
    #    exit()
    #    title += " (High Graphics Mode)"
    pygame.display.set_caption(title)

    # Initialize glut
    glutInit()

    # Enable Depth and Turn on Lights
    glEnable(GL_DEPTH_TEST)
    glEnable(GL_LIGHT0)
    glEnable(GL_LIGHTING)
    
    # Originally verticle faces or faces at a steep angle would be rendered
    # almost black. This was in a noon configuration - the light was
    # directly overhead. I tried a sunset configuration (looked just
    # like a sunset, but not bright enough for final gameplay) and an
    # afternoon configuration. The afternoon configuration is not perfect,
    # but it's a lot better.
    glLightfv(GL_LIGHT0, GL_POSITION, (Ground.HW * 0.5, 300.0, Ground.HW * 0.5))

    # Turn on Colors
    glColorMaterial(GL_FRONT, GL_DIFFUSE)
    glEnable(GL_COLOR_MATERIAL)

    # Set up the explosion displaylists
    Explosion.NO_EXPLOSION_FRAMES = explo_frames
    setup_explosion()

    # Set up the camera lens
    glMatrixMode(GL_PROJECTION)
    #gluPerspective(45.0, float(SCR[0])/float(SCR[1]), 0.1, 275.0)
    ## Test where the player can see all the way to the other end of the map
    gluPerspective(45.0, float(SCR[0])/float(SCR[1]), 0.1, Ground.DIAGONAL)
    glMatrixMode(GL_MODELVIEW)
    
    # NATURE

    # Make the sky blue
    glClearColor(0.25, 0.89, 0.92, 1.0)
    
    # Make the ground
    ground = Ground()
    ground.gen_list()

    hillposes = client.get_naturalobjs()[0]
    hills = [Hill(pos) for pos in hillposes]

    trees = [Tree(pos) for pos in client.get_naturalobjs()[1]]

    # Add the tanks
    tanks = []
    for card in client.hat:
        pos = client.poses_dict[card["name"]]
        tank = Tank(pos,
                    card["bout"],
                    (0.0,
                     1.0,
                     0.0),
                    card["name"],
                    card["color"]
                    )
        tanks.append(tank)
    #print "In main: len(tanks) is", len(tanks)

    # Take the player position from the client
    x, y, z = client.player.pos

    # Make allshapes
    player = Player((x, y, z), (0.0, 0.0, 1.0), (0.0, 1.0, 0.0), client.name, client, client.player.color)
    allshapes = [ground, player] + hills + trees + tanks # get all of the shapes
    drot = np.radians(1.0)
    # LifeBar
    lifebar = LifeBar(SCR)

    # Update the client's player class and tank list
    client.player = player
    #player.name = client.name
    client.tanks = tanks

    # Groups
    shells = []
    playershells = []
    mines = []

    # make a clock
    clock = pygame.time.Clock()

    game_over = False
    first_mainloop = True

    RELOAD_TIME = FPS * 10
    reloading = 0 # So they can fire in the initial 10 seconds of the game

    reloadingbar = ReloadingBar()
    
    # Victory Banner!
    victory_banner = None # cause we haven't won yet
    
    mine_reload = 0

    # Load Sounds
    crash = pygame.mixer.Sound("../data/sound/crash.wav")
    explosion = pygame.mixer.Sound("../data/sound/explosion.wav")

    frames_til_end = -1

    # On older computers, we were getting low FPS which meant the
    # reload times were off. Every second we'll adjust all the numbers
    # to match the data.
    fps_timer = 12

    last_update = 0

    while frames_til_end != 0:
        pygame.event.pump()
        # Pump connection
        client.Loop()

        if frames_til_end > 0:
            frames_til_end -= 1

        reloading -= 1
        mine_reload -= 1
        fps_timer -= 1
        
        # Clear Everything
        glLoadIdentity()
        glClear(GL_COLOR_BUFFER_BIT|GL_DEPTH_BUFFER_BIT)
               
        # Set up the observer
        # Choose the camera attributes based on whether we're playing or spectating
        if spectating:
            #print("spectating")
            pos = spectator.pos
            out = spectator.out
            up = spectator.up
        else:
            pos = player.pos.copy()
            pos[1] = 6.0
            out = player.tout
            up = player.up
        at = out + pos
        
        # We can't do gluLookAt(*pos, *at, *up) in Python 2.
        # https://stackoverflow.com/questions/53000998/unpacking-multiple-function-arguments-in-python-2
        # this means we'll have to do gluLookAt(*(pos + at + up)). And convert everything to lists as well.
        gluLookAt(*list(pos) + list(at) + list(up))
                                                                
        # Delete to avoid me making a bug later
        del pos, out, up

        # Obviously, this isn't causing the blackout.
        if fps_timer <= 0:
            FPS = int(round(clock.get_fps()))
            RELOAD_TIME = FPS * 10
            fps_timer = FPS * 0.25
            fps_timer = 2 # test out a version where high graphics doesn't suddenly slow down
            for shape in allshapes: 
                shape.update_fps()
            # Check that the server is still up and running
            # Actually, this doesn't work but that's OK for now
            client.test_connection()           

        if pygame.key.get_pressed()[pygame.K_f]:
            print(int(round(clock.get_fps())), "FPS")
            
        if pygame.key.get_pressed()[pygame.K_k]:
            # We need a reliable way to get out of it
            print("K")
            exit()

        if first_mainloop and player.alive:
            should_update = True

        for update in to_updates:
            if (update != client.name) and update in client.attrs:
                for tank in tanks:
                    if tank.name == update:
                        tank.recv_data(client.attrs[tank.name])
        to_updates = []

        if dead_tank:
            # This isn't causing the blackout
            to_remove = None
            for tank in tanks:
                if tank.name == dead_tank[2]:
                    to_remove = tank
            if to_remove:
                tanks.remove(to_remove)
                allshapes.remove(to_remove)
            allshapes.append(Explosion(np.array(dead_tank[0]), dead_tank[1]))
            explosion.play()
            dead_tank = None

        # Win?
        if (not tanks) and (playgame): # We are the only person left:
            print("Congrats! YOU WON!")
            should_update = True
            won = True
            playgame = False
            
            # Make the victory banner
            victory_banner = VictoryBanner(SCR)

            client.send_won()

        # Send handshake if dead
        if not playgame and client.player_alive and not won:
            # This isn't causing the blackout, I commented it out
            client.send_dead()

        # Make bullet on Space
        if pygame.key.get_pressed()[pygame.K_SPACE] and reloading <= 0 \
           and player.alive and frames_til_end <= -1:
            temp_tout = player.tout + (player.bout * player.speed) / Shell.SPEED
            temp_pos = np.array(player.pos) + Shell.START_DISTANCE * np.array(player.tout)
            shell = Shell(temp_pos, temp_tout, player.tangle,
                          client.name)
            client.send_bullet(temp_pos, temp_tout, player.tangle,
                               shell.id)
            shells.append(shell)
            playershells.append(shell)
            allshapes.append(shell)

            # Set reloading bar to full
            reloadingbar.fire()

            reloading = RELOAD_TIME
            
        if pygame.key.get_pressed()[pygame.K_b] and mine_reload <= 0 and player.alive and frames_til_end <= -1:
            mine = Mine(player.name, player.pos, player.color)
            client.send_mine(player.pos, player.color, mine.id)
            
            mines.append(mine)
            allshapes.append(mine)
            
            mine_reload = Mine.RELOAD

        if make_shell[0]:
            shell = Shell(make_shell[1], make_shell[2], make_shell[3],
                          make_shell[0], make_shell[4])
            shells.append(shell)
            allshapes.append(shell)

            make_shell = [False, (None, None, None), (None, None, None), (None, None, None), None]

        if not playgame and frames_til_end <= -1:
            if (not won) and (not spectating):
                
                # This isn't causing the blackout, I commented it out

                # We died, now enter spectate mode.
                spectating = True
                print("Started spectating")

                spectator = Spectator(player.pos, player.tout, player.up, player.tright, player.tangle)
                allshapes.append(spectator)
            #if won or len(tank): # Could I just change this to an 'else'?
            if (len(tanks) == 1) or won:
                frames_til_end = FPS * 3
                pygame.mixer.music.fadeout(3000)

        # Check for collisions
        # The ones that don't involve shells aren't causing "the blackout"
        for hill in hills:
            # Tank vs. Hill
            if collide_hill(player, hill, False, player.bout):

                # Calculate a vector away from the hill. Does that make sense? :P
                #away = normalize(hill.pos - player.pos)
                away = normalize(player.pos - hill.pos)
                
                # Back up the player so they aren't permanently stuck
                # Go a certain distance away from the hill
                player.pos += away * 10
                player.speed = 0.0

                should_update = True
                client.send_attributes()

            # Shell vs. hill
            for shell in shells:
                if collide_hill(shell, hill, is_shell = True):
                    shell.hill()

        for shell in playershells:
            pos = shell.pos.copy()
            pos[1] = 0.0
            pos = DummyPos(pos)
            for tank in tanks:
                if collide_tank(pos, tank, tank.bout) and (not shell.hit_hill) and (shell.name != tank.name):
                    # Tell the tank that it got hit
                    client.send_hit(tank.name, shell.id)
                    explosion.play()
                    shell.die()
                    
        for mine in mines:
            for tank in tanks:
                if collide_mine(mine, tank, tank.bout) and mine.name != tank.name:
                    client.send_minehit(tank.name, mine.id)

                    mine.die()
                    Mine.EXPLODE.play()
                    
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
                            tank.pos = (20 + COLLISION_SPRINGBACK) * \
                                         normalize(tank.pos - hill.pos) + \
                                         hill.pos
                        if collide_hill(player, hill, False, player.bout):
                            player.pos = (20 + COLLISION_SPRINGBACK) * \
                                         normalize(player.pos - hill.pos) + \
                                         hill.pos
                for tree in trees:
                    if collide_tank(tree, tank, tank.bout) and not tree.falling.any():
                        tree.fall(bad_tank.bright, 0.5)
                    if collide_tank(tree, player, tank.bout) and not tree.falling.any():
                        tree.fall(bad_tank.bright, 0.5)
                tank.speed = 0.0
                player.speed = 0.0
                should_update = True

        for shell in shells:
            for i in range(len(shell.pos)):
                if shell.pos[i] > Ground.HW or shell.pos[i] < -Ground.HW:
                    shell.hill()

        # Quit Game on X
        if pygame.event.get(pygame.QUIT) or pygame.key.get_pressed()[pygame.K_ESCAPE]:
            playgame = False

        #Update
        to_remove = []
        for i in range(len(allshapes) - 1, -1, -1):
            shape = allshapes[i]
            if not shape.alive:

                if shape in shells:
                    shells.remove(shape)

                if shape in playershells:
                    playershells.remove(shape)

                if shape in tanks:
                    tanks.remove(shape)
                    try:
                        del client.attrs[shape.name]
                    except(KeyError):
                        print("THIS BUG HAS BEEN HAUNTING ME SINCE 1983!! argh")
                        #print("shape.name:", shape.name)
                        #print("client.attrs", client.attrs)
                    
                if shape in mines:
                    mines.remove(shape)

                to_remove.append(allshapes[i])

            else:
                shape.update()

        if deadshell_id:
            for shell in shells:
                if shell.id == deadshell_id:
                    to_remove.append(shell)

            deadshell_id = None
            
        if deadmine_id:
            badmine = None
            for mine in mines:
                if mine.id == deadmine_id:
                    badmine = mine
                    to_remove.append(mine)
                    
            if badmine:
                mines.remove(badmine)
                    
            deadmine_id = None

        for shape in to_remove:
            allshapes.remove(shape)
            if shape in shells:
                shells.remove(shape)

        if first_mainloop:
            first_mainloop = False

        # Draw victory banner, if it exists
        if victory_banner:
            victory_banner.draw()

        # Update LifeBar
        if player.hits_left > 0:
            lifebar.draw()

        # Update ReloadingBar
        reloadingbar.draw(reloading)
        
        pygame.display.flip()
        clock.tick(FPS) # Limit the framerate, because the game doesn't handle different framerates well


if __name__ == "__main__":
    asyncio.run(main())
