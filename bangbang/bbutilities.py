# Oddly, unless we do this, print is still treated as a statement
# with parentheses around everything you print
from __future__ import print_function

import numpy as np
import random

from version import __version__

HW_CONST = 125

# Here's our message, we'll make it very specific to avoid potentially getting weird stuff.
MESSAGE = "Hello there. Do you happen to be a running server for Bang Bang " + __version__ + "?"

class DummyPos(object):
    def __init__(self, pos):
        self.pos = np.array(pos)


def input23(string):
    """Attempt to define an input function that is compatible with both Python 2 and Python 3.

Essentially, it will use raw_input if raw_input is defined and input otherwise.
"""

    #print("type(__builtins__):", type(__builtins__))
    #print(vars(__builtins__))

    # If raw_input is defined, we are using Python 2. In this case, we MUST use raw_input,
    # because in Python 2, input is similar to exec or eval().
    #if "raw_input" in vars(__builtins__):
    if "raw_input" in __builtins__:
        print("p2")
        return raw_input(string)
        
    # Using Python 3
    print("p3")
    return input(string)

def mag(v):
    """
    Returns the magnitude of a vector
    """
    return np.sqrt((v**2).sum())

def normalize(v):
    """
    Normalizes a vector
    """
    return v / mag(v)

def a2tf(array):
    """ Convert an array into a tuple of floats. """
    return (float(array[0]), float(array[1]), float(array[2]))

def read_obj_file(filename):
    """ Read an obj file and return a list of vertices,
    faces, and normals.

    This obj file *MUST* have vertex normals ("vn") in it.
    If it doesn't, the normals list will be empty. Faces is a list of
    (lists which contain vertex_indices), Vertices is a list of lists
    which contain coordinates, and Normals is a list of lists that are
    aligned with the vertex.

    In Blender, make sure to UNcheck the "Use UV" box in the export
    dialog."""
    # WITH OBJ FILES THE INDEXES ARE 1 OFF! THEY DO *not* START WITH ZERO!

    start = time()

    getfile = open(filename, 'r')

    vertices = []
    faces = []
    normals = []

    file_lines = getfile.readlines()

    for line in file_lines:
        line = line.strip()
        if line[:2] == "v ": # we can't say 'if line[:1] == "v"' because there's also going to be vn's
            coordinates = line.split()[1:] # we have to remove the v from the list
            vertices.append([float(coordinates[0]), float(coordinates[1]), float(coordinates[2])])

        if line[:3] == "vn ":
            numbers = line.split()[1:]
            normal = []
            for number in numbers:
                normal.append(float(number))
            normals.append(normal)

        if line[:2] == "f ":
            # faces are 6-tuples: 3 vertex_indices, then 3 normal_indices
            # OBJ INDICES ARE 1 OFF!
            indices = line[2:].split(" ")
            vertex_indices = []
            normal_indices = []
            for index in indices:
                vertex_normal = index.split("//")
                vertex_indices.append(int(vertex_normal[0]) - 1)
                normal_indices.append(int(vertex_normal[1]) - 1)

            six_tuple = tuple(vertex_indices + normal_indices)

            faces.append(six_tuple)

    getfile.close() # close the file

    return [vertices, faces, normals]

def draw_model(vertices, faces, normals):
    """ Draw a 3d model from vertices, faces, and normals.

    You can get them from a .ply file by calling read_ply_file()."""

    # Draw the model
    for face in faces:
        if len(face) == 3:
            glBegin(GL_POLYGON)
            for vertex_index in face:
                # tell them where the normal is
                normal = normals[vertex_index]
                glNormal(normal[0], normal[1], normal[2])

                # get the vertex
                vertex = vertices[vertex_index]

                # draw a little triangle
                glVertex(vertex[0], vertex[1], vertex[2])

            index = face[0]
            vertex = vertices[index]
            glVertex(vertex[0], vertex[1], vertex[2]) # the last point must close the triangle
            glEnd()

        if len(face) == 6:
            glBegin(GL_POLYGON)
            vertex_indices = face[:3]
            normal_indices = face[3:]
            for i in range(3):
                vertex_index = vertex_indices[i]
                normal_index = normal_indices[i]
                vertex = vertices[vertex_index]
                normal = normals[normal_index]
                glNormal(normal[0], normal[1], normal[2])
                glVertex(vertex[0], vertex[1], vertex[2])
            glEnd()

def collide_hill(obj, hill, is_shell = False, out = 0):
    """ Check for a collision between an object and a hill. """

    ret = False
    distance1 = 10
    distance2 = 10
    distance3 = 10

    if is_shell:
        # The famous distance equation
        distance = mag(obj.pos - hill.pos) - 20 # subtract the radius of the hill
    else:
        # It's a tank
        # Tank bases are in a ratio roughly 2:1.
        # We will account for this by checking for collisions with
        # three spheres.
        sphere1_pos = obj.pos - (out * 4.625)
        sphere2_pos = obj.pos + (out * 3.75)

        distance = mag(obj.pos - hill.pos) - 4 - 20# Get the center of the tank
        distance1 = mag(hill.pos - sphere1_pos) - 4 - 20
        distance2 = mag(hill.pos - sphere2_pos) - 4 - 20

    if (distance <= 0.0) or (distance1 <= 0.0) or (distance2 <= 0.0):
        ret = True

    return ret

def collide_tank(obj, tank, out):
    """ Check for a collision between an object and a tank. """

    ret = False

    # Tank bases are in a ratio roughly 2:1.
    # We will account for this by checking for collisions with
    # two spheres.
    sphere1_pos = tank.pos - (out * 4.625)
    sphere2_pos = tank.pos + (out * 3.75)

    distance = mag(obj.pos - tank.pos) - 4 # Get the center of the tank
    distance1 = mag(obj.pos - sphere1_pos) - 4
    distance2 = mag(obj.pos - sphere2_pos) - 4

    if (distance <= 0.0) or (distance1 <= 0.0) or (distance2 <= 0.0):
        ret = True

    return ret

def collide_mine(mine, tank, out):
    """ Check for a collision between a mine and a tank. """
    
    ret = False
    
    # Tank bases are in a ratio roughly 2:1.
    # We will account for this by checking for collisions with
    # two spheres.
    sphere1_pos = tank.pos - (out * 4.625)
    sphere2_pos = tank.pos + (out * 3.75)

    # If I understand correctly, I'm subtracting six because it's four for the tank and two for the mine.
    distance = mag(mine.pos - tank.pos) - 6
    distance1 = mag(mine.pos - sphere1_pos) - 6
    distance2 = mag(mine.pos - sphere2_pos) - 6

    if (distance <= 0.0) or (distance1 <= 0.0) or (distance2 <= 0.0):
        ret = True

    return ret

def collide_tanktank(tank1, tank2, out1, out2):

    ret = False

    tank1_spheres = []
    tank1_spheres.append(tank1.pos - (out1 * 4.625))
    tank1_spheres.append(tank1.pos + (out1 * 3.75))
    tank1_spheres.append(tank1.pos)

    tank2_spheres = []
    tank2_spheres.append(tank2.pos - (out2 * 4.625))
    tank2_spheres.append(tank2.pos + (out2 * 3.75))
    tank2_spheres.append(tank2.pos)

    for sphere1 in tank1_spheres:
        for sphere2 in tank2_spheres:
            distance = mag(sphere1 - sphere2)
            if distance - 4 <= 0.0:
                ret = True

    return ret

def random_tankpos(hillposes, hw):
    """ Return an x, y, and z position for a tank. """

    valid = False
    while not valid:
        bad_pos = False
        x = random.uniform(-hw, hw)
        y = 0.0
        z = random.uniform(-hw, hw)
        for pos in hillposes:
            if collide_hill(DummyPos((x, y, z)), DummyPos(pos)):
                bad_pos = True
        if not bad_pos:
            valid = True

    return np.array((x, y, z))

def offender(tank1, tank2):
    """ Did tank1 run into tank 2 or did tank2 run into tank1? """

    # Check if tank1 ran into tank 2
    tank1_pos = tank1.pos + tank1.bout * 5
    if collide_tank(DummyPos(tank1_pos), tank2, tank1.bout):
        ret = tank1
    else:
        ret = tank2

    return ret

class Shape(object):

    """ Base shape class. """

    gllist = "Unknown"

    def __init__(self, pos):
        """ You will almost always want to redefine this method! """

        self.pos = np.array(pos)
        self.alive = True

    def die(self):
        self.alive = False

    def get_alive(self):
        return self.alive

    def update_fps(self):
        pass

def naturalobj_poses(no_players, hw):
    """ Return a list of hill and poses. """

    # no_hills = no_players * 6
    # no_trees = no_players * 15
    no_hills = int(round(6.0 * np.sqrt(2 * no_players)))
    #no_trees = int(round(30.0 * np.sqrt(2 * no_players)))
    no_trees = int(round(15.0 * np.sqrt(2 * no_players)))

    hills = []
    for i in range(no_hills):
        x = random.randrange(-(hw - 30), (hw - 30))
        y = 0.0
        z = random.randrange(-(hw - 30), (hw - 30))
        hills.append((x, y, z))

    trees = []
    for i in range(no_trees):
        valid = False

        # No trees inside hills!
        while not valid:
            bad_tree = False
            x = random.randrange(-hw, hw)
            y = 0.0
            z = random.randrange(-hw, hw)
            for hill in hills:
                if collide_hill(DummyPos((x, y, z)), DummyPos(hill)):
                    bad_tree = True
                    break
            if not bad_tree:
                valid = True
        trees.append((x, y, z))
    return (hills, trees)
    
def ask_number(prompt):
    valid = False
    while not valid:
        try:
            prompt = int(input23(prompt))
        except(ValueError):
            print("Not a number. Please try again.")
        else:
            valid = True

            if prompt < 2:
                print("This is a multiplayer game. Two or more please!")
                exit()

    return prompt
