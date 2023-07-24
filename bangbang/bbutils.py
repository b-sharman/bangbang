import json
import random
import time
import typing

import numpy as np
import websockets.client
import websockets.server

import constants

# TODO: rename this constant
HW_CONST = 125

Message = typing.NewType("Message", dict)


class DummyPos(object):
    def __init__(self, pos):
        self.pos = np.array(pos)


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


def yaw(angle, out, up, right):
    """Returns new out vector after rotating angle degrees around UP."""
    # up fixed, out/right change
    return normalize(
        np.cos(np.radians(angle)) * out + np.sin(np.radians(angle)) * right
    )


def a2tf(array):
    """Convert an array into a tuple of floats."""
    return tuple([float[x] for x in array])


def read_obj_file(filename):
    """
    Read an obj file and return a list of vertices, faces, and normals.

    This obj file *MUST* have vertex normals ("vn") in it.
    If it doesn't, the normals list will be empty. Faces is a list of
    (lists which contain vertex_indices), Vertices is a list of lists
    which contain coordinates, and Normals is a list of lists that are
    aligned with the vertex.

    In Blender, make sure to UNcheck the "Use UV" box in the export
    dialog.
    """
    # WITH OBJ FILES THE INDEXES ARE 1 OFF! THEY DO *not* START WITH ZERO!

    with open(filename, "r") as f:
        file_lines = f.readlines()

    vertices = []
    faces = []
    normals = []

    for line in file_lines:
        line = line.strip()
        # we can't say 'if line[:1] == "v"' because there's also going to be vn's
        if line[:2] == "v ":
            coordinates = line.split()[1:]  # we have to remove the v from the list
            vertices.append([float(c) for c in coordinates])

        if line[:3] == "vn ":
            numbers = line.split()[1:]
            normals.append([float(n) for n in numbers])

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

            faces.append(tuple(vertex_indices + normal_indices))

    return [vertices, faces, normals]


def draw_model(vertices, faces, normals):
    """
    Draw a 3d model from vertices, faces, and normals.

    You can get them from a .ply file by calling read_ply_file().
    """

    # Draw the model
    for face in faces:
        if len(face) == 3:
            glBegin(GL_POLYGON)
            for vertex_index in face:
                # tell them where the normal is
                normal = normals[vertex_index]
                glNormal(*normal)

                # get the vertex
                vertex = vertices[vertex_index]

                # draw a little triangle
                glVertex(*vertex)

            index = face[0]
            vertex = vertices[index]
            # the last point must close the triangle
            glVertex(*vertex)
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
                glNormal(*normal)
                glVertex(*vertex)
            glEnd()


def collide_hill(obj, hill, is_shell=False, out=0):
    """Check for a collision between an object and a hill."""
    ret = False
    distance1 = 10
    distance2 = 10
    distance3 = 10

    if is_shell:
        # The famous distance equation
        distance = mag(obj.pos - hill.pos) - 20  # subtract the radius of the hill
    else:
        # It's a tank
        # Tank bases are in a ratio roughly 2:1.
        # We will account for this by checking for collisions with
        # three spheres.
        sphere1_pos = obj.pos - (out * 4.625)
        sphere2_pos = obj.pos + (out * 3.75)

        distance = mag(obj.pos - hill.pos) - 4 - 20  # Get the center of the tank
        distance1 = mag(hill.pos - sphere1_pos) - 4 - 20
        distance2 = mag(hill.pos - sphere2_pos) - 4 - 20

    if (distance <= 0.0) or (distance1 <= 0.0) or (distance2 <= 0.0):
        ret = True

    return ret


def collide_tank(obj, tank, out):
    """Check for a collision between an object and a tank."""
    # Tank bases are in a ratio roughly 2:1.
    # We will account for this by checking for collisions with
    # two spheres.
    sphere1_pos = tank.pos - (out * 4.625)
    sphere2_pos = tank.pos + (out * 3.75)

    distance = mag(obj.pos - tank.pos) - 4  # Get the center of the tank
    distance1 = mag(obj.pos - sphere1_pos) - 4
    distance2 = mag(obj.pos - sphere2_pos) - 4

    if (distance <= 0.0) or (distance1 <= 0.0) or (distance2 <= 0.0):
        return True
    return False


def collide_mine(mine, tank, out):
    """Check for a collision between a mine and a tank."""
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
        return True
    return False


def collide_tanktank(tank1, tank2, out1, out2):
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
                return True

    return False


def random_tankpos(hillposes, hw):
    """Return an x, y, and z position for a tank."""

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
    """Did tank1 run into tank 2 or did tank2 run into tank1?"""

    # Check if tank1 ran into tank 2
    tank1_pos = tank1.pos + tank1.bout * 5
    if collide_tank(DummyPos(tank1_pos), tank2, tank1.bout):
        return tank1
    else:
        return tank2


class Shape(object):
    """Base shape class."""

    gllist = "Unknown"

    def __init__(self):
        self.clock = time.time()
        self.alive = True

    def delta_time(self):
        """
        Return the time elapsed in seconds since the last call to delta_time.

        If delta_time is being called for the first time, return the time since
        __init__ was called.
        """
        new_time = time.time()
        diff = new_time - self.clock
        self.clock = new_time
        return diff

    def die(self):
        self.alive = False


def naturalobj_poses(no_players, hw):
    """Return a list of hill and poses."""
    no_hills = int(round(6.0 * np.sqrt(2 * no_players)))
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
    while True:
        try:
            ret = int(input(prompt))
        except ValueError:
            print("Not a number. Please try again.")
            continue
        if ret < 2:
            print("This is a multiplayer game. Two or more please!")
            continue
        break

    return ret


def is_message_valid(message: Message) -> None:
    """Raise ValueError if message does not meet protocol."""
    # TODO: This is already hard to read and will only become more difficult. It might
    # be worthwhile to consider an external data validation library like cerberus.

    # must be a dict
    if type(message) != dict:
        raise ValueError("message is not a dict")

    # must have type
    if "type" not in message:
        raise ValueError("message has no type")

    # type must be specified in constants.Msg
    if message["type"] not in iter(constants.Msg):
        raise ValueError("invalid message type")

    # id must be int
    if "id" in message and not isinstance(message["id"], int):
        raise ValueError("client id is not int")

    # name must be str
    if "name" in message and not isinstance(message["name"], str):
        raise ValueError("client name is not str")

    # rq must be specified in constants.Rq
    if "rq" in message and message["rq"] not in iter(constants.Rq):
        raise ValueError("invalid message rq")

    # type-specific requirements
    match message["type"]:
        case constants.Msg.APPROVE:
            # APPROVE must have id
            if "id" not in message:
                raise ValueError("APPROVE message does not have id")
            # APPROVE must have state
            if "state" not in message:
                raise ValueError("APPROVE message does not have state")

        # ID must have id
        case constants.Msg.ID if "id" not in message:
            raise ValueError("ID message does not have id")

        # GREET must have name
        case constants.Msg.GREET if "name" not in message:
            raise ValueError("GREET message does not have name")

        # REQUEST must have rq
        case constants.Msg.REQUEST if "rq" not in message:
            raise ValueError("REQUEST message does not have rq")


class _BBSharedProtocol:
    """WebSocketClientProtocol with send() that enforces JSON format."""

    async def send(self, message: Message) -> None:
        """
        Serialize message to json and call the regular send on it.

        This method also enforces message validity; it is decorated by
        check_message_valid.
        """
        is_message_valid(message)
        await super().send(json.dumps(message))


class BBClientProtocol(_BBSharedProtocol, websockets.client.WebSocketClientProtocol):
    pass


class BBServerProtocol(_BBSharedProtocol, websockets.server.WebSocketServerProtocol):
    pass
