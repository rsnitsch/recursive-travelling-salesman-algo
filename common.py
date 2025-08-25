#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Common functionality for travelling-salesman-problem algorithms.
"""
import random

from math import ceil, sqrt

from shapely.geometry import LineString
from rtree import index


class Node(object):
    """Abstract TSP Node."""

    def __init__(self, *args, **kwargs):
        pass

    def get_travel_costs(self, other_node, ceil_2d):
        """
        Returns the costs for travelling from this node to the given node.
        
        Raises NotImplemented unless overwritten.
        """
        raise NotImplementedError("get_travel_costs() must be implemented in subclasses")

    def get_nearest_neighbor(self, candidates, ceil_2d):
        """
        Calculates the travel costs for each of the given candidate nodes
        and returns the candidate with the minimum costs along with the
        according minimum costs. This means it returns a 2-tuple:
        (nearest_neighbor, nearest_distance)
        """
        nearest_neighbor = candidates[0]
        nearest_distance = self.get_travel_costs(candidates[0], ceil_2d)
        for i in range(1, len(candidates)):
            candidate_distance = self.get_travel_costs(candidates[i], ceil_2d)
            if candidate_distance < nearest_distance:
                nearest_distance = candidate_distance
                nearest_neighbor = candidates[i]
        return (nearest_neighbor, nearest_distance)


class CoordinateNode(Node):
    """
    TSP Node for the metric TSP with a X- and a Y-coordinate.
    
    The distance between 2 CoordinateNodes is calculated using
    Pythagoras' theorem (and converting the result to rounded integer for
    TSPLIB compatibility).
    """

    def __init__(self, x, y, *args, **kwargs):
        self.x = x
        self.y = y

    def get_travel_costs(self, other_node, ceil_2d):
        euc_distance = sqrt((other_node.x - self.x)**2 + (other_node.y - self.y)**2)
        if ceil_2d:
            return int(ceil(euc_distance))
        else:
            return int(round(euc_distance))

    def __str__(self):
        return "CN(%s, %s)" % (self.x, self.y)


def ccw(p: CoordinateNode, q: CoordinateNode, r: CoordinateNode):
    """
    Check whether three points p, q, r are arranged in a counter-clockwise order.

    This function computes the orientation of the triplet (p, q, r).
    If the result is True, the sequence of points makes a "left turn"
    (counter-clockwise); otherwise, it is clockwise or collinear.

    Args:
        p, q, r: Points with attributes `x` and `y`.

    Returns:
        bool: True if points are in counter-clockwise order, False otherwise.
    """
    return (r.y - p.y) * (q.x - p.x) > (q.y - p.y) * (r.x - p.x)


def segments_intersect(a: CoordinateNode, b: CoordinateNode, c: CoordinateNode, d: CoordinateNode):
    """
    Determine whether two line segments (a-b) and (c-d) intersect.

    Uses orientation tests (via ccw) to check intersection without
    computing actual intersection points.
    This is a standard computational geometry method that works in O(1).

    Args:
        a, b, c, d: Points with attributes `x` and `y`.
                    Represent the endpoints of two line segments: ab and cd.

    Returns:
        bool: True if the segments intersect (proper crossing), False otherwise.
    """
    return (ccw(a, c, d) != ccw(b, c, d)) and (ccw(a, b, c) != ccw(a, b, d))


class Route(list):

    def get_total_costs(self, ceil_2d):
        """Returns the total travel costs for this route."""
        total = 0
        for i in range(len(self) - 1):
            total += self[i].get_travel_costs(self[i + 1], ceil_2d)
        total += self[len(self) - 1].get_travel_costs(self[0], ceil_2d)
        return total

    def intersection_cleanup(self):
        """
        Iteratively remove geometric intersections (via 2-opt moves) using an R-Tree
        for near-O(n log n) candidate filtering.
        """
        n = len(self)

        # initial edge + shapely line representation
        edges = [(self[i], self[(i + 1) % n]) for i in range(n)]
        lines = [LineString([(a.x, a.y), (b.x, b.y)]) for a, b in edges]

        idx = index.Index((k, l.bounds, None) for k, l in enumerate(lines))

        improved = True
        while improved:
            improved = False
            for i, l1 in enumerate(lines):
                for j in idx.intersection(l1.bounds):
                    if j <= i:
                        continue
                    l2 = lines[j]
                    if l1.crosses(l2):
                        a, b = self[i], self[(i + 1) % n]
                        c, d = self[j], self[(j + 1) % n]
                        if not (b is c or a is d):  # skip adjacent edges
                            # Perform 2-opt move
                            self[i + 1:j + 1] = reversed(self[i + 1:j + 1])

                            # rebuild edges & index after the swap
                            n = len(self)
                            edges = [(self[k], self[(k + 1) % n]) for k in range(n)]
                            lines = [LineString([(p.x, p.y), (q.x, q.y)]) for p, q in edges]
                            idx = index.Index((k, l.bounds, None) for k, l in enumerate(lines))
                            improved = True
                            break
                if improved:
                    break
        return self


def generate_random_nodes(count, seed=0, max_size=500):
    """
    Generates count nodes with coordinates between 0 and max_size.
    
    Uses seed to initialize the random number generator.
    
    Returns a list of nodes.
    """
    random.seed(seed)

    nodes = []
    for i in range(count):
        nodes.append(CoordinateNode(random.randint(0, max_size), random.randint(0, max_size)))

    return nodes


def load_nodes_from_tsplib_file(filename):
    """
    Loads all nodes specified in the given tsplib-file.
    
    Only euclidean instances are supported (EUC_2D or CEIL_2D).
    """
    nodes = []
    ceil_2d = None

    with open(filename, "r", encoding='utf-8') as fh:
        for line in fh:
            line = line.strip()

            assert len(line) > 0

            if line.startswith("EDGE_WEIGHT_TYPE"):
                if line.endswith("EUC_2D"):
                    ceil_2d = False
                elif line.endswith("CEIL_2D"):
                    ceil_2d = True
                else:
                    raise ValueError("only EUC_2D or CEIL_2D instances can be loaded")
                continue

            if line[0].isdigit():
                index, x, y = [float(i) for i in filter(lambda x: len(x) > 0, line.strip().split(" "))]
                nodes.append(CoordinateNode(x, y))
            elif line == "EOF":
                break

    if ceil_2d is None:
        raise ValueError("could not determine EDGE_WEIGHT_TYPE from file")

    return nodes, ceil_2d


optimal_solutions = {
    'a280': 2579,
    'ali535': 202339,
    'att48': 10628,
    'att532': 27686,
    'bayg29': 1610,
    'bays29': 2020,
    'berlin52': 7542,
    'bier127': 118282,
    'brazil58': 25395,
    'brd14051': 469385,
    'brg180': 1950,
    'burma14': 3323,
    'ch130': 6110,
    'ch150': 6528,
    'd1291': 50801,
    'd15112': 1573084,
    'd1655': 62128,
    'd18512': 645238,
    'd198': 15780,
    'd2103': 80450,
    'd493': 35002,
    'd657': 48912,
    'dantzig42': 699,
    'dsj1000': 18660188,
    'eil101': 629,
    'eil51': 426,
    'eil76': 538,
    'fl1400': 20127,
    'fl1577': 22249,
    'fl3795': 28772,
    'fl417': 11861,
    'fnl4461': 182566,
    'fri26': 937,
    'gil262': 2378,
    'gr120': 6942,
    'gr137': 69853,
    'gr17': 2085,
    'gr202': 40160,
    'gr21': 2707,
    'gr229': 134602,
    'gr24': 1272,
    'gr431': 171414,
    'gr48': 5046,
    'gr666': 294358,
    'gr96': 55209,
    'hk48': 11461,
    'kroA100': 21282,
    'kroA150': 26524,
    'kroA200': 29368,
    'kroB100': 22141,
    'kroB150': 26130,
    'kroB200': 29437,
    'kroC100': 20749,
    'kroD100': 21294,
    'kroE100': 22068,
    'lin105': 14379,
    'lin318': 42029,
    'linhp318': 41345,
    'nrw1379': 56638,
    'p654': 34643,
    'pa561': 2763,
    'pcb1173': 56892,
    'pcb3038': 137694,
    'pcb442': 50778,
    'pla33810': 66048945,
    'pla7397': 23260728,
    'pla85900': 142382641,
    'pr1002': 259045,
    'pr107': 44303,
    'pr124': 59030,
    'pr136': 96772,
    'pr144': 58537,
    'pr152': 73682,
    'pr226': 80369,
    'pr2392': 378032,
    'pr264': 49135,
    'pr299': 48191,
    'pr439': 107217,
    'pr76': 108159,
    'rat195': 2323,
    'rat575': 6773,
    'rat783': 8806,
    'rat99': 1211,
    'rd100': 7910,
    'rd400': 15281,
    'rl11849': 923288,
    'rl1304': 252948,
    'rl1323': 270199,
    'rl1889': 316536,
    'rl5915': 565530,
    'rl5934': 556045,
    'si1032': 92650,
    'si175': 21407,
    'si535': 48450,
    'st70': 675,
    'sw24978': 855597,
    'swiss42': 1273,
    'ts225': 126643,
    'tsp225': 3916,
    'u1060': 224094,
    'u1432': 152970,
    'u159': 42080,
    'u1817': 57201,
    'u2152': 64253,
    'u2319': 234256,
    'u574': 36905,
    'u724': 41910,
    'ulysses16': 6859,
    'ulysses22': 7013,
    'usa13509': 19982859,
    'vm1084': 239297,
    'vm1748': 336556
}


def tsplib_get_optimal_solution(tsp_instance):
    global optimal_solutions
    return optimal_solutions[tsp_instance]
