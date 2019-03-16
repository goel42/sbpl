from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

from bc_gym_planning_env.utilities.path_tools import parallel_distances, get_blit_mask
from builtins import range
import numpy as np

import cv2

from bc_gym_planning_env.utilities.coordinate_transformations import normalize_angle, diff_angles


def get_pixel_footprint(angle, robot_footprint, map_resolution, fill=True):
    '''
    Return a binary image of a given robot footprint, in pixel coordinates,
    rotated over the appropriate angle range.
    Point (0, 0) in world coordinates is in the center of the image.
    angle_range: if a 2-tuple, the robot footprint will be rotated over this range;
        the returned footprint results from superimposing the footprint at each angle.
        If a single number, a single footprint at that angle will be returned
    robot_footprint: n x 2 numpy array with ROS-style footprint (x, y coordinates),
        in metric units, oriented at 0 angle
    map_resolution:
    :param angle Float: orientation of the robot
    :param robot_footprint array(N, 2)[float64]: n x 2 numpy array with ROS-style footprint (x, y coordinates),
        in metric units, oriented at 0 angle
    :param map_resolution Float: length in metric units of the side of a pixel
    :param fill bool: if True, the footprint will be solid; if False, only the contour will be traced
    :return array(K, M)[uint8]: image of the footprint drawn on the image in white
    '''
    assert not isinstance(angle, tuple)
    angles = [angle]
    m = np.empty((2, 2, len(angles)))  # stack of 2 x 2 matrices to rotate the footprint across all desired angles
    c, s = np.cos(angles), np.sin(angles)
    m[0, 0, :], m[0, 1, :], m[1, 0, :], m[1, 1, :] = (c, -s, s, c)
    rot_pix_footprints = np.rollaxis(np.dot(robot_footprint / map_resolution, m), -1)  # n_angles x n_footprint_corners x 2
    # From all the possible footprints, get the outer corner
    footprint_corner = np.maximum(np.amax(rot_pix_footprints.reshape(-1, 2), axis=0),
                                  -np.amin(rot_pix_footprints.reshape(-1, 2), axis=0))
    pic_half_size = np.ceil(footprint_corner).astype(np.int32)
    int_footprints = np.round(rot_pix_footprints).astype(np.int32)

    # int_footprints = np.floor(rot_pix_footprints).astype(np.int32)
    # get unique int footprints to save time; using http://stackoverflow.com/questions/16970982/find-unique-rows-in-numpy-array
    flat_int_footprints = int_footprints.reshape(len(angles), -1)
    row_view = np.ascontiguousarray(flat_int_footprints).view(np.dtype((np.void, flat_int_footprints.dtype.itemsize * flat_int_footprints.shape[1])))
    _, idx = np.unique(row_view, return_index=True)
    unique_int_footprints = int_footprints[idx]
    kernel = np.zeros(2 * pic_half_size[::-1] + 1, dtype=np.uint8)
    for f in unique_int_footprints:
        if fill:
            cv2.fillPoly(kernel, [f + pic_half_size], (255, 255, 255))
        else:
            cv2.polylines(kernel, [f + pic_half_size], 1, (255, 255, 255))
    return kernel


def world_to_pixel_floor(world_coords, origin, resolution):
    """
    Convert a numpy set of world coordinates (... x 2 numpy array)
    to pixel coordinates, given origin ((x, y) in world coordinates)
    and resolution (in world units per pixel)
    Instead of rounding, this uses floor.
    Python implementation of SBPL CONTXY2DISC
    #define CONTXY2DISC(X, CELLSIZE) (((X)>=0)?((int)((X)/(CELLSIZE))):((int)((X)/(CELLSIZE))-1))

    The returned array is of type np.int, same shape as world_coords

    :param world_coords: An Array(..., 2)[float] array of (x, y) world coordinates in meters.
    :param origin: A (x, y) point representing the location of the origin in meters.
    :param resolution: Resolution in meters/pixel.
    :returns: An Array(..., 2)[int] of (x, y) pixel coordinates
    """
    assert len(origin) == 2

    if not isinstance(world_coords, np.ndarray):
        world_coords = np.asarray(world_coords)
    if not isinstance(origin, np.ndarray):
        origin = np.asarray(origin)
    assert world_coords.shape[world_coords.ndim - 1] == 2
    # (((X)>=0)?((int)((X)/(CELLSIZE))):((int)((X)/(CELLSIZE))-1))
    return np.floor((world_coords - origin) / resolution).astype(np.int)


def world_to_pixel_sbpl(world_coords, origin, resolution):
    """
    Convert a numpy set of world coordinates (... x 2 numpy array)
    to pixel coordinates, given origin ((x, y) in world coordinates)
    and resolution (in world units per pixel)
    Instead of rounding, this uses floor.
    Python implementation of SBPL CONTXY2DISC
    #define CONTXY2DISC(X, CELLSIZE) (((X)>=0)?((int)((X)/(CELLSIZE))):((int)((X)/(CELLSIZE))-1))

    The returned array is of type np.int, same shape as world_coords

    :param world_coords: An Array(..., 2)[float] array of (x, y) world coordinates in meters.
    :param origin: A (x, y) point representing the location of the origin in meters.
    :param resolution: Resolution in meters/pixel.
    :returns: An Array(..., 2)[int] of (x, y) pixel coordinates
    """
    assert len(origin) == 2

    if not isinstance(world_coords, np.ndarray):
        world_coords = np.asarray(world_coords)
    if not isinstance(origin, np.ndarray):
        origin = np.asarray(origin)
    assert world_coords.shape[world_coords.ndim - 1] == 2

    # (((X)>=0)?((int)((X)/(CELLSIZE))):((int)((X)/(CELLSIZE))-1))

    result = ((world_coords - origin) / np.float(resolution)).astype(np.int)
    result[world_coords < 0] -= 1
    return result


def pixel_to_world_centered(pixel_coords, origin, resolution):
    '''
    Convert a numpy set of pixel coordinates (... x 2 numpy array)
    to world coordinates, given origin ((x, y) in world coordinates) and
    resolution (in world units per pixel)
    Gives center of the pixel like SBPL
    #define DISCXY2CONT(X, CELLSIZE) ((X)*(CELLSIZE) + (CELLSIZE)/2.0)

    The returned array is of type np.float32, same shape as pixel_coords
    '''
    pixel_coords = np.asarray(pixel_coords)
    assert pixel_coords.shape[pixel_coords.ndim - 1] == 2
    return pixel_coords.astype(np.float64) * resolution + np.array(origin, dtype=np.float64) + resolution*0.5



def ensure_float_numpy(data):
    '''
    Transforms python array to numpy or makes sure that numpy array is float32 or 64
    '''
    if isinstance(data, (list, tuple)):
        return np.array(data, dtype=float)
    else:
        assert(data.dtype in [np.float, np.float32])
        return data


def refine_path(data, delta, angle_delta=None):
    '''
    Insert points in the path if distance between existing points along a path is larger than delta.
    There are two ways to insert points given a constraint on a distance delta:
    Imagine path is from 0 to 1 and constraint is 0.49.
     - option 1:
        step with delta from the begging till the end:
        (0, 0.49, 0.98, 1)
        most of the time distance is equal to delta, but there might be really short steps like the last one
     - option 2:
        determine how many points to insert and make equal steps (1/0.49 + 1 = 3 intervals
        (0, 0.333, 0.666, 1)
        distance between points is smaller than delta, but there are no really small steps

    This function uses option 2.

    Angle is interpolated if angle_delta is not None. Interpolation happens
        by copying the second point in a consecutive pair several times
        with different angles.

    :param data: a np array of n x (x, y) or (x, y, angle) elements
    :param delta: maximum distance between points
    :param angle_delta: if not None, angle differences bigger than this will be
        interpolated; interpolation happens by copying the second point in
        a consecutive pair several times with different angles. Angle must be
        provided if not None.
    :returns regularized_path: a np array of m x (x, y) or (x, y, angle) elements
    '''
    if isinstance(data, (list, tuple)):
        data = np.array(data, dtype=float)
    else:
        assert(data.dtype in [np.float, np.float32])
    if data.shape[1] not in (2, 3):
        raise Exception("This function takes n x (x, y) or n x (x, y, angle) arrays")
    if angle_delta is not None and data.shape[1] != 3:
        raise Exception("Path does not include angles but angle interpolation was requested")
    xy = data[:, :2]
    segment_lengths = np.linalg.norm(np.diff(xy, axis=0), axis=1)
    if angle_delta is not None:
        angles = diff_angles(data[1:, 2], data[:-1, 2])
    pieces = []
    for i, d in enumerate(segment_lengths):
        if d > delta:
            # interpolate all coordinates one by one (e.g. x, y)
            npoints = int(d / delta) + 2
            interpolated = [np.linspace(data[i, j], data[i+1, j], num=npoints)
                            for j in range(2)]
            # copy angle between interpolations
            if data.shape[1] == 3:
                interpolated.append(np.ones((npoints,), dtype=float)*data[i, 2])
            piece = np.vstack(interpolated).T
            # cut down the end in order to join with the next piece
            pieces.append(piece[:-1])
        else:
            pieces.append(data[i])
        if angle_delta is not None and np.abs(angles[i]) > angle_delta:
            n_points = int(np.abs(angles[i]) / angle_delta) + 1
            interpolated_angles = normalize_angle(data[i, 2] + angles[i] / n_points * np.arange(n_points))
            pieces.append([[data[i + 1, 0], data[i + 1, 1], a] for a in interpolated_angles])

    # add path endpoint
    pieces.append(data[-1])
    return np.vstack(pieces)


def orient_path(path, robot_pose=None, final_pose=None, max_movement_for_turn_in_place=0.0):
    """ This function orient the path
    For those points have large movement (not turn-in-place points), use the diff angle as the pose heading. For those
    turn-in-place points, use not turn-in-places points before and after to interpolate.

    Final pose is only used to decide the pose angle so that it's guaranted that the position of oriented_path and
    path are exactly the same.

    :param path: np.ndarray: N * 2 path points
    :param robot_pose: np.ndarray: 3 * 1 (x, y, theta), current robot pose
    :param final_pose: np.ndarray: 3 * 1 (x, y, theta), desired last pose
    :param max_movement_for_turn_in_place: float: points within this distance are considered as turn-in-place
    :return: np.ndarray: N * 3 path with orientation
    """
    if len(path) < 2:
        return path
    path = ensure_float_numpy(path)

    # keep the position the same
    oriented_path = np.zeros((len(path), 3), dtype=path.dtype)
    oriented_path[:, :2] = path[:, :2]

    path_diff = path[1:, :] - path[0: -1, :]
    path_angles = np.arctan2(path_diff[:, 1], path_diff[:, 0])

    # if given final pose, use it as last pose
    oriented_path[:-1, 2] = path_angles
    oriented_path[-1, 2] = final_pose[2] if final_pose is not None else oriented_path[-2, 2]

    turn_in_place_points = np.hypot(path_diff[:, 0], path_diff[:, 1]) < max_movement_for_turn_in_place
    if robot_pose is not None and turn_in_place_points[0]:
        oriented_path[0, 2] = robot_pose[2]
        turn_in_place_points[0] = False

    # TODO: optimize this
    left_not_turn_in_place_indices = np.zeros(len(path_angles), dtype=int)
    for i in range(1, len(left_not_turn_in_place_indices)):
        left_not_turn_in_place_indices[i] = left_not_turn_in_place_indices[i-1] if turn_in_place_points[i] else i
    right_not_turn_in_place_indices = np.zeros(len(path_angles), dtype=int)
    right_not_turn_in_place_indices[-1] = len(path_angles)
    for i in range(len(path_angles)-2, -1, -1):
        right_not_turn_in_place_indices[i] = right_not_turn_in_place_indices[i+1] if turn_in_place_points[i] else i

    for i in np.where(turn_in_place_points)[0]:
        left_index = left_not_turn_in_place_indices[i]
        right_index = right_not_turn_in_place_indices[i]
        oriented_path[i, 2] = (oriented_path[left_index, 2] * (right_index - i) +
                               oriented_path[right_index, 2] * (i - left_index)) / (right_index - left_index)
    return oriented_path


def normalize_angle_0_2pi(angle):
    # get to the range from -2PI, 2PI
    if np.abs(angle) > 2 * np.pi:
        angle = angle - ((int)(angle / (2 * np.pi))) * 2 * np.pi

    # get to the range 0, 2PI
    if angle < 0:
        angle += 2 * np.pi

    return angle


def angle_cont_to_discrete(angle, num_angles):
    '''
    Python port of ContTheta2Disc from sbpl utils (from continuous angle to one of uniform ones)
    :param angle float: float angle
    :param num_angles int: number of angles in 2*pi range
    :return: discrete angle
    '''
    theta_bin_size = 2.0 * np.pi / num_angles
    return (int)(normalize_angle_0_2pi(angle + theta_bin_size / 2.0) / (2.0 * np.pi) * num_angles)


def angle_discrete_to_cont(angle_cell, num_angles):
    '''
    Python port of DiscTheta2Cont from sbpl utils (from discrete angle to continuous)
    :param angle_cell int: discrete angle
    :param num_angles int: number of angles in 2*pi range
    :return: discrete angle
    '''
    bin_size = 2*np.pi/num_angles
    return normalize_angle(angle_cell*bin_size)


def path_velocity(path):
    '''
    :param path: n x 4 array of (t, x, y, angle)
    :return: arrays of v and w along the path
    '''
    path = np.asarray(path)
    diffs = np.diff(path, axis=0)
    dt = diffs[:, 0]
    assert (dt > 0).all()

    # determine direction of motion
    dxy = diffs[:, 1:3]
    sign = np.sign(np.cos(path[:, 3])[:-1]*dxy[:, 0] + np.sin(path[:, 3])[:-1]*dxy[:, 1])
    sign[sign == 0.] = np.sign(np.sin(path[:, 3])[:-1]*dxy[:, 1])[sign == 0.]

    ds = np.linalg.norm(dxy, axis=1)*sign
    dangle = diffs[:, 3]
    dangle[dangle < -np.pi] += 2*np.pi
    dangle[dangle > np.pi] -= 2*np.pi
    # large angular velocities are not supported
    if not (np.abs(dangle) < np.pi).all():
        bad_indices = (np.abs(dangle) > np.pi).nonzero()
        raise Exception("Path has missing/corrupted angle data at indices: %s. Data: %s" %
                        (bad_indices, dangle[bad_indices]))
    return ds/dt, dangle/dt


def pose_distances(pose0, pose1):
    '''
    Determine linear and angular difference between poses
    :param pose0: (x, y, angle) or array of such poses
    :param pose1: (x, y, angle) or array of such poses
    :return: linear and angular distances
    '''
    pose0 = np.asarray(pose0)
    pose1 = np.asarray(pose1)
    assert pose0.shape == pose1.shape

    return np.hypot(pose0[..., 0] - pose1[..., 0], pose0[..., 1] - pose1[..., 1]),\
        np.abs(diff_angles(pose0[..., 2], pose1[..., 2]))


def limit_path_index(path, max_dist, max_angle=np.inf, min_length=0):
    """
    From the given path take only the number of points that will not exceed
    the distance or angle criterion (whichever is less).
    :param max_dist - max distance along the path
    :param max_angle - max rotation along the path
    :param min_length - don't cut shorter than that

    :return: cutoff index that should *NOT* be included in the path.
    """
    path = np.asarray(path, dtype=float)
    if len(path) < 2:
        return len(path)

    d_path = np.diff(path, axis=0)

    cum_dist = np.cumsum(np.hypot(d_path[:, 0], d_path[:, 1]))
    cum_angle = np.cumsum(np.abs(np.angle(np.exp(1j * d_path[:, 2]))))
    min_dist_cutoff = len(path) if cum_dist[-1] <= min_length else (1 + np.argmax(cum_dist > min_length))
    dist_cutoff = len(path) if cum_dist[-1] <= max_dist else (1 + np.argmax(cum_dist > max_dist))
    angle_cutoff = len(path) if cum_angle[-1] <= max_angle else (1 + np.argmax(cum_angle > max_angle))
    cutoff = min(len(path), max(min_dist_cutoff, min(dist_cutoff, angle_cutoff)))
    return cutoff


def find_reached_indices(pose, segment, spatial_precision, angular_precision, parallel_distance_threshold=None):
    """
    Walk along the path and determine which point we have reached; a point
        is reached if it is so either wrt the original path or the
        deformed path.

    :param pose: (x, y, theta) of the robot
    :param segment: m x 3 points corresponding to the segment deformed by the elastic planner
    :return: all reached indices
    """
    assert len(segment) > 0
    if parallel_distance_threshold is None:
        parallel_distance_threshold = -spatial_precision / 9
    dist = np.hypot(segment[:, 0] - pose[0], segment[:, 1] - pose[1])
    angle = np.abs(diff_angles(pose[2], segment[:, 2]))
    parallel_dist = parallel_distances(pose, segment)
    reached_idx = np.where(np.logical_and(np.logical_and(dist < spatial_precision, angle < angular_precision),
                                          parallel_dist >= parallel_distance_threshold))[0]
    return reached_idx


def find_last_reached(pose, segment, spatial_precision, angular_precision, parallel_distance_threshold=None):
    """
    Walk along the path and determine which point we have reached; a point
        is reached if it is so either wrt the original path or the
        deformed path.

    :param pose: (x, y, theta) of the robot
    :param segment: m x 3 points corresponding to the segment deformed by the elastic planner
    :return: the max index in the segment that is reached
    """
    reached_idx = find_reached_indices(pose, segment, spatial_precision, angular_precision, parallel_distance_threshold)
    if len(reached_idx):
        return reached_idx[-1]
    return None


def compute_robot_area(resolution, robot_footprint):
    '''
    Computes robot footprint area in pixels
    '''
    return float(np.count_nonzero(get_pixel_footprint(0., robot_footprint, resolution)))
