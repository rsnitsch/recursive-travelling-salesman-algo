#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Recursive-fold-algorithm (RFA) for metric travelling-salesman-problems.
"""
import random
from common import CoordinateNode, Route
from mst import build_mst_tree, mst_fold_sequence, find_foldable_leaf


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

    def fold(self, nodes, renderer=None):
        """Fold nodes using the strategy defined in the subclass."""
        raise NotImplementedError("fold() must be implemented in subclasses")


class FoldingStrategyRandomWithNearestNeighbor(FoldingStrategy):
    """
    Nodes are picked in random order. Each node is folded with its nearest neighbor.
    """

    def fold(self, nodes, renderer=None):
        nodes = list(nodes)
        if renderer:
            renderer.visualize(nodes)

        while not len(nodes) <= 3:
            node1 = random.choice(nodes)
            nodes.remove(node1)

            node2, dist = node1.get_nearest_neighbor(nodes)
            nodes.remove(node2)

            nodes.append(RFANode((node1.x + node2.x) / 2, (node1.y + node2.y) / 2, (node1, node2)))

            if renderer:
                renderer.visualize(nodes)

        return nodes


class FoldingStrategyMST(FoldingStrategy):
    """
    Nodes are folded using a minimum spanning tree (MST) strategy.

    The MST is built from the nodes, and the folding is done according to the MST structure.
    The folding sequence is determined by the MST edges.
    """

    def fold(self, nodes, renderer=None):
        if renderer:
            renderer.visualize(nodes)

        if len(nodes) <= 3:
            return list(nodes)

        remaining_nodes = list(nodes)
        while len(remaining_nodes) > 3:
            # Build MST tree
            root = build_mst_tree(remaining_nodes)

            # Get folding sequence
            fold_sequence = mst_fold_sequence(root)

            for node1, node2 in fold_sequence:
                if node1 in remaining_nodes and node2 in remaining_nodes:
                    remaining_nodes.remove(node1)
                    remaining_nodes.remove(node2)

                    # Create folded node at midpoint
                    folded_node = RFANode((node1.x + node2.x) / 2, (node1.y + node2.y) / 2, (node1, node2))
                    remaining_nodes.append(folded_node)

                    if renderer:
                        renderer.visualize(remaining_nodes)

                    # Stop if we have 3 or fewer nodes
                    if len(remaining_nodes) <= 3:
                        break

        return remaining_nodes


class FoldingStrategyMSTBottomUp(FoldingStrategy):
    """
    Nodes are folded using a bottom-up MST strategy.

    The MST is built from the nodes, and the folding is done systematically
    starting from the leaves, folding them with their parent nodes.
    """

    def fold(self, nodes, renderer=None):
        if renderer:
            renderer.visualize(nodes)

        if len(nodes) <= 3:
            return list(nodes)

        remaining = list(nodes)

        while len(remaining) > 3:
            # Build MST for current remaining nodes
            root = build_mst_tree(remaining)

            # Find a leaf node to fold with its parent
            leaf_parent_pair = find_foldable_leaf(root)

            if not leaf_parent_pair:
                # If no clear leaf-parent pair, fall back to nearest neighbor
                import random
                node1 = random.choice(remaining)
                remaining.remove(node1)
                node2, _ = node1.get_nearest_neighbor(remaining)
                remaining.remove(node2)
            else:
                parent, leaf = leaf_parent_pair
                remaining.remove(parent.original)
                remaining.remove(leaf.original)
                node1, node2 = parent.original, leaf.original

            # Create folded node
            folded = RFANode((node1.x + node2.x) / 2, (node1.y + node2.y) / 2, (node1, node2))
            remaining.append(folded)

            if renderer:
                renderer.visualize(remaining)

        return remaining


class UnfoldingStrategy(object):

    def unfold(self, nodes_to_unfold, renderer=None):
        """Unfold nodes using the strategy defined in the subclass."""
        raise NotImplementedError("unfold() must be implemented in subclasses")


class UnfoldingStrategyBreadthFirst(UnfoldingStrategy):
    """Unfolding strategy that processes nodes in breadth-first manner.

    The list of folded nodes is processed repeatedly. During each iteration,
    only the nodes with the maximum depth are unfolded.
    """

    def unfold(self, nodes_to_unfold, renderer=None):
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

                assert len(nodes) == len_nodes + 1, "Unfolding did not increase number of nodes by 1."
                len_nodes += 1
                i += 2

                if renderer:
                    renderer.visualize(nodes)

            if len_before == len(nodes):
                return nodes
