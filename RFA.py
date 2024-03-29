#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Recursive-fold-algorithm (RFA) for metric travelling-salesman-problems.
"""
import random
from common import CoordinateNode, Route, TSPAlgorithm


class RFANode(CoordinateNode):

    def __init__(self, x, y, children):
        CoordinateNode.__init__(self, x, y)
        self.children = children


class RFA(TSPAlgorithm):
    """Recursive-Fold-Algorithm"""

    def fold(self):
        pass

    def unfold(self):
        pass


class RFABasic(RFA):
    """
    A very simple RFA implementation.
    
    *Folding:* Nodes are picked in random order. Each node is folded with its nearest neighbor. This process
    is repeated until 3 nodes remain.

    *Unfolding:* The nodes in the preliminary route are unfolded sequentially (breadth-first approach). This process
    is repeated until all of the original nodes have been restored.

    @todo: Try to use kdtree for faster nearest-neighbor search.
    """

    def run(self):
        self.save_start_time()

        folded = self.fold()
        route = Route(self.unfold(folded))

        self.save_end_time()

        return route

    def fold(self):
        nodes = list(self.nodes)

        while not len(nodes) <= 3:
            node1 = random.choice(nodes)
            nodes.remove(node1)

            node2, dist = node1.get_nearest_neighbor(nodes)
            nodes.remove(node2)

            nodes.append(RFANode((node1.x + node2.x) / 2, (node1.y + node2.y) / 2, (node1, node2)))

        return nodes

    def unfold(self, nodes_to_unfold):
        nodes = list(nodes_to_unfold)
        while True:
            len_before = len(nodes)

            for i in range(len(nodes)):
                if not isinstance(nodes[i], RFANode):
                    continue

                before = nodes[i - 1] if i > 0 else nodes[len(nodes) - 1]
                after = nodes[i + 1] if i < len(nodes) - 1 else nodes[0]

                node1, node2 = nodes[i].children
                route1 = Route([before, node1, node2, after])
                route2 = Route([before, node2, node1, after])

                nodes.remove(nodes[i])

                if route1.get_total_costs() < route2.get_total_costs():
                    nodes.insert(i, node2)
                    nodes.insert(i, node1)
                else:
                    nodes.insert(i, node1)
                    nodes.insert(i, node2)

            if len_before == len(nodes):
                return nodes
