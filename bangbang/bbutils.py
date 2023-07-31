# TODO: add type hints to the functions in this file

import json
import random
import time
import typing

import numpy as np
import websockets.client
import websockets.server

import collisions
import constants

Message = typing.NewType("Message", dict)


def mag(v):
    """Return the magnitude of a vector."""
    return np.sqrt((v**2).sum())


def normalize(v):
    """Return a normalized vector."""
    return v / mag(v)


def yaw(angle, out, up, right):
    """Return new out vector after rotating `angle` degrees around `up`."""
    # up fixed, out/right change
    return normalize(
        np.cos(np.radians(angle)) * out + np.sin(np.radians(angle)) * right
    )


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
    """Draw a 3d model from vertices, faces, and normals."""

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


def random_tankpos(hillposes, hw):
    """Return an x, y, and z position for a tank."""

    valid = False
    while not valid:
        bad_pos = False
        x = random.uniform(-hw, hw)
        y = 0.0
        z = random.uniform(-hw, hw)
        for pos in hillposes:
            if collisions.collide_hill(DummyPos((x, y, z)), DummyPos(pos)):
                bad_pos = True
        if not bad_pos:
            valid = True

    return np.array((x, y, z))


def offender(tank1, tank2):
    """Did tank1 run into tank 2 or did tank2 run into tank1?"""

    # Check if tank1 ran into tank 2
    tank1_pos = tank1.pos + tank1.bout * 5
    if collisions.collide_tank(DummyPos(tank1_pos), tank2, tank1.bout):
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


def is_message_valid(message: Message) -> None:
    """Raise ValueError if message does not meet protocol."""
    # TODO: This is already hard to read and will only become more difficult. It might
    # be worthwhile to consider an external data validation library like cerberus.

    # must be a dict
    if not isinstance(message, dict):
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

    # actions must be specified in constants.Action
    if "actions" in message:
        for a in message["actions"]:
            if a not in iter(constants.Action):
                raise ValueError(f"invalid message action '{a}'")

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

        # REQUEST must have actions
        case constants.Msg.REQUEST if "actions" not in message:
            raise ValueError("REQUEST message does not have actions")

        # START must have ...
        case constants.Msg.START:
            for must_have in ("ground_hw", "hill_poses", "tree_poses", "states"):
                if must_have not in message:
                    raise ValueError(f"START message does not have {must_have}")


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
