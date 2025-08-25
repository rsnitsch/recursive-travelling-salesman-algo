#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Recursive-fold-algorithm (RFA) for metric travelling-salesman-problems.
"""
import random
from typing import List

from common import CoordinateNode, Node, Route
from ui import Renderer


class RFANode(CoordinateNode):

    def __init__(self, x, y, children):
        CoordinateNode.__init__(self, x, y)
        self.children = children

        child1, child2 = children
        if isinstance(child1, RFANode) and isinstance(child2, RFANode):
            self.depth = max(child1.depth, child2.depth) + 1
        elif isinstance(child1, RFANode):
            self.depth = child1.depth + 1
        elif isinstance(child2, RFANode):
            self.depth = child2.depth + 1
        else:
            self.depth = 1


class FoldingStrategy(object):

    def fold(self, nodes, ceil_2d, renderer):
        """Fold nodes using the strategy defined in the subclass."""
        raise NotImplementedError("fold() must be implemented in subclasses")


class FoldingStrategyRandomWithNearestNeighbor(FoldingStrategy):
    """
    Nodes are picked in random order. Each node is folded with its nearest neighbor.
    """

    def fold(self, nodes: List[Node], ceil_2d: bool, renderer: Renderer):
        nodes = list(nodes)
        if renderer:
            renderer.visualize(nodes)

        while not len(nodes) <= 3:
            node1 = random.choice(nodes)
            nodes.remove(node1)

            node2, dist = node1.get_nearest_neighbor(nodes, ceil_2d)
            nodes.remove(node2)

            nodes.append(RFANode((node1.x + node2.x) / 2, (node1.y + node2.y) / 2, (node1, node2)))

            if renderer:
                renderer.visualize(nodes)

        return nodes


class FoldingStrategyOutsideIn(FoldingStrategy):
    """
    Outside-in folding with fixed center point calculated at the beginning.
    """

    def fold(self, nodes: List[Node], ceil_2d: bool, renderer):
        nodes = list(nodes)
        if renderer:
            renderer.visualize(nodes)

        if len(nodes) <= 3:
            return nodes

        # Calculate fixed center point from initial node set
        center_x = sum(node.x for node in nodes) / len(nodes)
        center_y = sum(node.y for node in nodes) / len(nodes)

        while len(nodes) > 3:
            # Find the node furthest from the fixed center
            furthest_node = max(nodes, key=lambda node: (node.x - center_x)**2 + (node.y - center_y)**2)

            nodes.remove(furthest_node)

            if not nodes:
                break

            # Find nearest neighbor
            nearest_neighbor, _ = furthest_node.get_nearest_neighbor(nodes, ceil_2d)
            nodes.remove(nearest_neighbor)

            # Create folded node
            folded_node = RFANode((furthest_node.x + nearest_neighbor.x) / 2,
                                  (furthest_node.y + nearest_neighbor.y) / 2, (furthest_node, nearest_neighbor))
            nodes.append(folded_node)

            if renderer:
                renderer.visualize(nodes)

        return nodes


class UnfoldingStrategy(object):

    def unfold(self, nodes_to_unfold, ceil_2d, renderer):
        """Unfold nodes using the strategy defined in the subclass."""
        raise NotImplementedError("unfold() must be implemented in subclasses")


class UnfoldingStrategyBreadthFirst(UnfoldingStrategy):
    """Unfolding strategy that processes nodes in breadth-first manner.

    The list of folded nodes is processed repeatedly. During each iteration,
    only the nodes with the maximum depth are unfolded.
    """

    def __init__(self):
        self.enable_local_2opt = False

    def unfold(self, nodes_to_unfold, ceil_2d, renderer):
        nodes = list(nodes_to_unfold)

        while True:
            len_before = len(nodes)

            max_depth = 0
            for node in nodes:
                if isinstance(node, RFANode):
                    max_depth = max(max_depth, node.depth)

            i = 0
            len_nodes = len(nodes)
            while i < len_nodes:
                if not isinstance(nodes[i], RFANode):
                    i += 1
                    continue
                if nodes[i].depth < max_depth:
                    # Only unfold the nodes that are at the maximum depth.
                    i += 1
                    continue

                before = nodes[i - 1] if i > 0 else nodes[len(nodes) - 1]
                after = nodes[i + 1] if i < len(nodes) - 1 else nodes[0]

                node1: Node = nodes[i].children[0]
                node2: Node = nodes[i].children[1]
                route1 = Route([before, node1, node2, after])
                route2 = Route([before, node2, node1, after])

                nodes.remove(nodes[i])

                if route1.get_total_costs(ceil_2d) < route2.get_total_costs(ceil_2d):
                    nodes.insert(i, node2)
                    nodes.insert(i, node1)
                    inserted = [node1, node2]
                else:
                    nodes.insert(i, node1)
                    nodes.insert(i, node2)
                    inserted = [node2, node1]

                assert len(nodes) == len_nodes + 1, "Unfolding did not increase number of nodes by 1."
                len_nodes += 1
                i += 2

                # New: Local 2-opt around the inserted nodes
                if self.enable_local_2opt:
                    nodes = self.local_2opt_segment(nodes, inserted, ceil_2d, radius=5)

                if renderer:
                    renderer.visualize(nodes)

            if len_before == len(nodes):
                return nodes

    def local_2opt_segment(self, tour, inserted_nodes, ceil_2d, radius=5):
        """
        Perform a local 2-opt in the neighborhood of the inserted nodes.
        """
        changed = True
        while changed:
            changed = False
            for node in inserted_nodes:
                idx = tour.index(node)
                i_start = max(0, idx - radius)
                i_end = min(len(tour), idx + radius)

                for i in range(i_start, i_end - 2):
                    for j in range(i + 2, i_end):
                        if j - i == 1:
                            continue

                        a: Node = tour[i]
                        b: Node = tour[(i + 1) % len(tour)]
                        c: Node = tour[j]
                        d: Node = tour[(j + 1) % len(tour)]

                        old_cost = a.get_travel_costs(b, ceil_2d) + c.get_travel_costs(d, ceil_2d)
                        new_cost = a.get_travel_costs(c, ceil_2d) + b.get_travel_costs(d, ceil_2d)

                        if new_cost < old_cost:
                            # 2-opt move
                            tour[i + 1:j + 1] = reversed(tour[i + 1:j + 1])
                            changed = True
        return tour


class UnfoldingStrategyBreadthFirstWithLocal2Opt(UnfoldingStrategyBreadthFirst):
    """
    Like UnfoldingStrategyBreadthFirst, but after each unfolding step,
    a local 2-opt optimization around the inserted nodes is performed.
    """

    def __init__(self):
        super().__init__()
        self.enable_local_2opt = True
