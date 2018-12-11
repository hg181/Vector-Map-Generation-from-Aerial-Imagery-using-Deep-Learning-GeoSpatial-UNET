"""Post Processing of vector and Raster dataset"""
import shapefile
import numpy as np
from scipy.spatial import ConvexHull
import fiona
from fiona.crs import from_epsg
from shapely.geometry import mapping, Polygon
from shapely.geometry import MultiPolygon
import os
from pyproj import Proj, transform


# Mininum bounding box/ axis aligned bounding box
def minimum_bounding_rectangle(points):
    """
    Find the smallest bounding rectangle for a set of points.
    Returns a set of points representing the corners of the bounding box.

    :param points: an nx2 matrix of coordinates
    :rval: an nx2 matrix of coordinates
    """
    from scipy.ndimage.interpolation import rotate
    pi2 = np.pi/2.

    # get the convex hull for the points
    hull_points = points[ConvexHull(points).vertices]

    # calculate edge angles
    edges = np.zeros((len(hull_points)-1, 2))
    edges = hull_points[1:] - hull_points[:-1]

    angles = np.zeros((len(edges)))
    angles = np.arctan2(edges[:, 1], edges[:, 0])

    angles = np.abs(np.mod(angles, pi2))
    angles = np.unique(angles)

    # find rotation matrices

    rotations = np.vstack([
        np.cos(angles),
        np.cos(angles-pi2),
        np.cos(angles+pi2),
        np.cos(angles)]).T
    #     rotations = np.vstack([
    #         np.cos(angles),
    #         -np.sin(angles),
    #         np.sin(angles),
    #         np.cos(angles)]).T
    rotations = rotations.reshape((-1, 2, 2))

    # apply rotations to the hull
    rot_points = np.dot(rotations, hull_points.T)

    # find the bounding points
    min_x = np.nanmin(rot_points[:, 0], axis=1)
    max_x = np.nanmax(rot_points[:, 0], axis=1)
    min_y = np.nanmin(rot_points[:, 1], axis=1)
    max_y = np.nanmax(rot_points[:, 1], axis=1)

    # find the box with the best area
    areas = (max_x - min_x) * (max_y - min_y)
    best_idx = np.argmin(areas)

    # return the best box
    x1 = max_x[best_idx]
    x2 = min_x[best_idx]
    y1 = max_y[best_idx]
    y2 = min_y[best_idx]
    r = rotations[best_idx]

    rval = np.zeros((4, 2))
    rval[0] = np.dot([x1, y2], r)
    rval[1] = np.dot([x2, y2], r)
    rval[2] = np.dot([x2, y1], r)
    rval[3] = np.dot([x1, y1], r)

    return rval


def aabbox(path_shp):
    path_output = os.path.join(os.path.dirname(
        path_shp), os.path.splitext(path_shp)[0] + '_bbox.shp')

    sf = shapefile.Reader(path_shp)

    # Reading in Fiona
    fio = fiona.open(path_shp, 'r')

    # Extracting coordinates
    coord_sys = fio.crs_wkt

    shapes = sf.shapes()
    num_shp = len(shapes)
    poly = []

    # Getting records
    rec = sf.records()

    for n in range(num_shp):
        if rec[n][0] == 0:  # Removing '0' background value
            continue
        else:
            coord = np.asarray(shapes[n].points)
            bbox = np.asarray(minimum_bounding_rectangle(coord))
            b = np.append(bbox[j], [bbox[j][0]], axis=0)
            poly.append(Polygon(b))

    schema = {
        'geometry': 'Polygon',
        'properties': {'id': 'int',
                       'Area': 'float'},
    }

    # Write a new Shapefile
    with fiona.open(path_output, 'w', crs=coord_sys, driver='ESRI Shapefile', schema=schema) as c:
        # If there are multiple geometries, put the "for" loop here
        for i in range(len(poly)):
            c.write({
                'geometry': mapping(Polygon(poly[i])),
                'properties': {'id': i,
                               'Area': area[i]},
            })