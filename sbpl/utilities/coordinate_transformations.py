from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
import numpy as np
from bc_gym_planning_env.utilities.coordinate_transformations import homogenize, normalize_angle, rotation_matrix


def transform_to_homogeneous_matrix(transform):
    """
    Represent transform as a 3x3 matrix that can be multiplied together to get a composite transform.
    Multiplying this on a vector of points augment with row of ones, project points between coordinate frames.

    If left-applied (i.e. as np.dot(M, point)), it first rotates and then translates
    :param transform: 3 numbers: 2 translation array [meters] and scalar rotation [radians]
    :return: 3x3 homogeneous transformation matrix
    """
    h = np.identity(3)
    h[:2, :2] = rotation_matrix(transform[2])
    h[:2, 2] = transform[:2]
    return h


def project_poses(transform, poses):
    """
    Python implementation of project_poses for the reference
    """
    if len(poses) == 0:
        return poses
    ph = homogenize(poses[:, :2])
    ph_moved = np.dot(transform_to_homogeneous_matrix(transform), ph.T).T
    ph_moved[:, 2] = normalize_angle(poses[:, 2] + transform[2])
    return ph_moved


def from_egocentric_to_global(ego_poses, ego_pose_in_global_coordinates):
    return project_poses(
        np.asarray(ego_pose_in_global_coordinates),
        ego_poses
    )
