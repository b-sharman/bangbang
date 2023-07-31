# TODO: make constants for all the magic numbers in this file

import numpy as np

import bbutils

def collide_hill(obj, hill, is_shell=False, out=0):
    """
    Check for a collision between an object and a hill.

    obj and hill can either be objects with pos attributes or poses themselves.
    """
    ret = False
    distance1 = 10
    distance2 = 10
    distance3 = 10

    obj_pos = obj.pos if hasattr(obj, "pos") else obj
    if not isinstance(obj_pos, np.ndarray):
        obj_pos = np.array(obj_pos)
    hill_pos = hill.pos if hasattr(hill, "pos") else hill
    if not isinstance(hill_pos, np.ndarray):
        hill_pos = np.array(hill_pos)

    if is_shell:
        # The famous distance equation
        distance = bbutils.mag(obj_pos - hill_pos) - 20  # subtract the radius of the hill
    else:
        # It's a tank
        # Tank bases are in a ratio roughly 2:1.
        # We will account for this by checking for collisions with
        # three spheres.
        sphere1_pos = obj_pos - (out * 4.625)
        sphere2_pos = obj_pos + (out * 3.75)

        distance = bbutils.mag(obj_pos - hill_pos) - 4 - 20  # Get the center of the tank
        distance1 = bbutils.mag(hill_pos - sphere1_pos) - 4 - 20
        distance2 = bbutils.mag(hill_pos - sphere2_pos) - 4 - 20

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

    distance = bbutils.mag(obj.pos - tank.pos) - 4  # Get the center of the tank
    distance1 = bbutils.mag(obj.pos - sphere1_pos) - 4
    distance2 = bbutils.mag(obj.pos - sphere2_pos) - 4

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
    distance = bbutils.mag(mine.pos - tank.pos) - 6
    distance1 = bbutils.mag(mine.pos - sphere1_pos) - 6
    distance2 = bbutils.mag(mine.pos - sphere2_pos) - 6

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
            distance = bbutils.mag(sphere1 - sphere2)
            if distance - 4 <= 0.0:
                return True

    return False
