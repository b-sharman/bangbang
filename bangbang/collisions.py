import numpy as np

import constants
import utils_3d


def collide_hill(hill_pos: np.ndarray, obj_pos: np.ndarray) -> bool:
    """Return True if a hill and another object are colliding, False otherwise."""
    return utils_3d.mag(hill_pos - obj_pos) < constants.Hill.RADIUS


def collide_hill_tank(hill_pos: np.ndarray, tank_pos: np.ndarray, tank_bout: np.ndarray) -> bool:
    """Return True if a hill and a tank are colliding, False otherwise."""
    # This should be slightly faster than any() and list comprehension because it
    # might allow for less iterations. That said, list comprehensions are fast, so
    # I'd have to benchmark to be sure.
    for tank_sphere in tank_collision_spheres(tank_pos, tank_bout):
        if utils_3d.mag(tank_sphere - hill_pos) < constants.Hill.RADIUS + constants.Tank.RADIUS:
            return True
    return False


def collide_tank(tank_pos: np.ndarray, obj_pos: np.ndarray, tank_bout: np.ndarray) -> bool:
    """Return True if a tank and another object are colliding, False otherwise."""
    for tank_sphere in tank_collision_spheres(tank_pos, tank_bout):
        if utils_3d.mag(tank_sphere - obj_pos) < constants.Tank.RADIUS:
            return True
    return False


def collide_tank_mine(tank_pos: np.ndarray, mine_pos: np.ndarray, tank_bout: np.ndarray) -> bool:
    """Return True if a tank and a mine are colliding, False otherwise."""
    for tank_sphere in tank_collision_spheres(tank_pos, tank_bout):
        if utils_3d.mag(tank_sphere - mine_pos) < constants.Tank.RADIUS + constants.Mine.RADIUS:
            return True
    return False


def collide_tank_tank(
    tank1_pos: np.ndarray, tank2_pos: np.ndarray, out1: np.ndarray, out2: np.ndarray
) -> bool:
    """Return True if two tanks are colliding, False otherwise."""
    for sphere1 in tank_collision_spheres(tank1_pos, out1):
        for sphere2 in tank_collision_spheres(tank2_pos, out2):
            if utils_3d.mag(sphere1 - sphere2) < constants.Tank.RADIUS * 2:
                return True
    return False


def collide_shell_world(shell_pos: np.ndarray, ground_hw: int) -> bool:
    """Return True if a shell passes the boundaries of the playing area."""
    for dimension in shell_pos:
        if abs(dimension) > ground_hw:
            return True
    return False


def tank_collision_spheres(tank_pos: np.ndarray, tank_bout: np.ndarray) -> tuple[np.ndarray]:
    """Return the centers of three spheres used for tank collision."""
    return (
        tank_pos,
        tank_pos - (tank_bout * constants.Tank.COLLISION_SPHERE_BACK),
        tank_pos + (tank_bout * constants.Tank.COLLISION_SPHERE_FRONT),
    )
