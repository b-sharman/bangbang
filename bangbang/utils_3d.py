import numpy as np
from OpenGL.GL import *
from OpenGL.GLU import *

import constants


def exec_raw(full_name: str) -> None:
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


def mag(v: np.ndarray) -> np.ndarray:
    """Return the magnitude of a vector."""
    return np.sqrt((v**2).sum())


def normalize(v: np.ndarray) -> np.ndarray:
    """Return a normalized vector."""
    # return 0 for an array of zeros
    if np.all(v == 0.0): return v
    return v / mag(v)


def read_obj_file(filename: str) -> tuple[list[list]]:
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

    return (vertices, faces, normals)


def setup_explosion(no_explosion_frames, no_mine_frames) -> tuple[list["gllist"]]:
    """
    Create gllists for Explosions and MineExplosions.

    Return explosion base gllists, explosion turret gllists, and mine explosion gllists.
    """
    base_gllists = []
    for i in range(1, no_explosion_frames + 1):
        gllist = glGenLists(1)
        glNewList(gllist, GL_COMPILE)
        exec_raw(f"../data/models/explosions/base_explosion_{i:06}.raw")
        glEndList()
        base_gllists.append(gllist)

    turret_gllists = []
    for i in range(1, no_explosion_frames + 1):
        gllist = glGenLists(1)
        glNewList(gllist, GL_COMPILE)
        exec_raw(f"../data/models/explosions/turret_explosion_{i:06}.raw")
        glEndList()
        turret_gllists.append(gllist)

    mine_gllists = []
    for i in range(1, no_mine_frames + 1):
        gllist = glGenLists(1)
        glNewList(gllist, GL_COMPILE)
        exec_raw(f"../data/models/explosions/mine_explosion_{i:06}.raw")
        glEndList()
        mine_gllists.append(gllist)

    return (base_gllists, turret_gllists, mine_gllists)


def window2view(pts: list[tuple[float]], distance=constants.OVERLAY_DISTANCE) -> list[tuple[float]]:
    """Convert window coordinates to 3D coordinates."""
    return [
        gluUnProject(
            pt[0],
            pt[1],
            distance,
            glGetDoublev(GL_MODELVIEW_MATRIX),
            glGetDoublev(GL_PROJECTION_MATRIX),
            glGetIntegerv(GL_VIEWPORT)
        )
        for pt in pts
    ]


def yaw(angle: float, out: np.ndarray, right: np.ndarray) -> np.ndarray:
    """Return new out vector after rotating `angle` degrees."""
    # up fixed, out/right change
    return normalize(
        np.cos(np.radians(angle)) * out + np.sin(np.radians(angle)) * right
    )
