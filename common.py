#!/usr/bin/env python
# coding=UTF-8

"""
Package:    RFA demonstration
Author:     Robert Nitsch
Source:     http://www.robertnitsch.de/de:informatik:rfa-traveling-salesman

This package demonstrates the recursive fold algorithm (RFA) for metric
traveling-salesman-problems. See the URL above for details (german).
"""

from math import *
import sys
import time
import random

class Node(object):
    """Abstract TSP Node."""
    def __init__(self, *args, **kwargs):
        pass

    def get_travel_costs(self, other_node):
        """
        Returns the costs for traveling from this node to the given node.
        
        Raises NotImplemented unless overwritten.
        """
        raise NotImplemented

    def get_nearest_neighbor(self, candidates):
        """
        Calculates the travel costs for each of the given candidate nodes
        and returns the candidate with the minimum costs along with the
        according minimum costs. This means it returns a 2-tuple:
        (nearest_neighbor, nearest_distance)
        """
        nearest_neighbor = candidates[0]
        nearest_distance = self.get_travel_costs(candidates[0])
        for i in range(1, len(candidates)):
            candidate_distance = self.get_travel_costs(candidates[i])
            if candidate_distance < nearest_distance:
                nearest_distance = candidate_distance
                nearest_neighbor = candidates[i]
        return (nearest_neighbor, nearest_distance)
    
class CoordinateNode(Node):
    """
    TSP Node for the metric TSP with a X- and a Y-coordinate.
    
    The distance between 2 CoordinateNodes is calculated using
    Pythagoras' theorem (and converting the result to integer for
    TSPLIB compatibility).
    """
    
    def __init__(self, x, y, *args, **kwargs):
        self.x = x
        self.y = y

    def get_travel_costs(self, other_node):
        return int(sqrt((other_node.x - self.x)**2 + (other_node.y - self.y)**2))
        #return sqrt((other_node.x - self.x)**2 + (other_node.y - self.y)**2)

    def __str__(self):
        return "CN(%s, %s)" % (self.x, self.y)
    
class Route(list):
    def get_total_costs(self):
        """Returns the total travel costs for this route."""
        sum = 0
        
        for i in range(len(self)-1):
            sum += self[i].get_travel_costs(self[i+1])
        sum += self[len(self)-1].get_travel_costs(self[0])
        
        return sum
    
class TSPAlgorithm(object):
    """Abstract TSPAlgorithm."""
    def __init__(self, nodes):
        self.nodes      = tuple(nodes)
        self.t_started  = 0
        self.t_end      = 0

    def run(self):
        """Returns a Route containing all the nodes which have been
        handed over to the constructor."""
        raise NotImplemented

    def save_start_time(self):
        """Children should execute this method each time run() is called."""
        self.t_started = time.time()

    def save_end_time(self):
        """Children should execute this method after each time run() has been
        executed."""
        self.t_end = time.time()

    def get_runtime(self):
        """Calculates the time difference between the most recent calls of
        save_start_time() and save_end_time()."""
        return round(self.t_end - self.t_started, 3)

def generate_random_nodes(count, seed=0, max_size=500):
    """
    Generates count nodes with coordinates between 0 and max_size.
    
    Uses seed to initialize the random number generator.
    
    Returns a list of nodes.
    """
    random.seed(seed)

    nodes = []
    for i in range(count):
        nodes.append(CoordinateNode(random.randint(0,max_size),
                                    random.randint(0,max_size)))

    return nodes

def load_nodes_from_tsplib_file(filename):
    """
    Loads all nodes specified in the given tsplib-file.
    
    Only EUC_2D-format is supported.
    """
    nodes = []

    with open(filename, "r") as fh:
        for line in fh:
            line = line.strip()

            assert len(line) > 0

            if line.startswith("EDGE_WEIGHT_TYPE"):
                assert line.endswith("EUC_2D"), \
                       "only EUC_2D instances can be loaded"
                continue

            if line[0].isdigit():
                index, x, y = [float(i) for i in filter(lambda x: len(x) > 0, line.strip().split(" "))]
                nodes.append(CoordinateNode(x, y))
            elif line == "EOF":
                break

    return nodes

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
