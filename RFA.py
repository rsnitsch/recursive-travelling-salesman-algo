#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Recursive-fold-algorithm (RFA) for metric travelling-salesman-problems.
"""
import random
from common import CoordinateNode, Route, TSPAlgorithm
from mst import build_mst_tree, mst_fold_sequence, find_foldable_leaf


def unfold_breadth_first(nodes_to_unfold):
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


class RFANode(CoordinateNode):

    def __init__(self, x, y, children):
        CoordinateNode.__init__(self, x, y)
        self.children = children


class RFA(TSPAlgorithm):
    """Recursive-Fold-Algorithm"""

    def run(self):
        self.save_start_time()

        folded = self.fold()
        route = Route(self.unfold(folded))

        self.save_end_time()

        return route

    def fold(self):
        raise NotImplementedError("fold() must be implemented in subclasses")

    def unfold(self):
        raise NotImplementedError("unfold() must be implemented in subclasses")


class RFABasic(RFA):
    """
    A very simple RFA implementation.
    
    *Folding:* Nodes are picked in random order. Each node is folded with its nearest neighbor. This process
    is repeated until 3 nodes remain.

    *Unfolding:* The nodes in the preliminary route are unfolded sequentially (breadth-first approach). This process
    is repeated until all of the original nodes have been restored.

    @todo: Try to use kdtree for faster nearest-neighbor search.
    """

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
        return unfold_breadth_first(nodes_to_unfold)


class RFAMST(RFA):
    """
    A more sophisticated RFA implementation that uses a minimum spanning tree (MST) for folding.

    *Folding:* A minimum spanning tree is created from the nodes. The nodes are folded in a systematic manner
    following the MST structure, prioritizing leaf nodes and their parents.

    *Unfolding:* The nodes in the preliminary route are unfolded sequentially (breadth-first approach). This process
    is repeated until all of the original nodes have been restored.
    """

    def fold(self):
        """Fold nodes using MST-guided strategy."""
        return RFAMST.mst_bottom_up_fold(list(self.nodes))

    def unfold(self, nodes_to_unfold):
        """Unfold using breadth-first approach."""
        return unfold_breadth_first(nodes_to_unfold)

    @staticmethod
    def mst(nodes):
        """
        Main MST function for RFA folding.
        Returns folded nodes using MST-guided strategy.
        """
        if len(nodes) <= 3:
            return list(nodes)

        # Build MST tree
        root = build_mst_tree(nodes)

        # Get folding sequence
        fold_sequence = mst_fold_sequence(root)

        # Apply folding sequence
        remaining_nodes = list(nodes)

        for node1, node2 in fold_sequence:
            if node1 in remaining_nodes and node2 in remaining_nodes:
                remaining_nodes.remove(node1)
                remaining_nodes.remove(node2)

                # Create folded node at midpoint
                folded_node = RFANode((node1.x + node2.x) / 2, (node1.y + node2.y) / 2, (node1, node2))
                remaining_nodes.append(folded_node)

                # Stop if we have 3 or fewer nodes
                if len(remaining_nodes) <= 3:
                    break

        return remaining_nodes

    @staticmethod
    def mst_bottom_up_fold(nodes):
        """
        Alternative MST folding that works bottom-up from leaves.
        More systematic than the basic random approach.
        """
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

        return remaining


# Alternative implementation with more control
class RFAMSTAdvanced(RFA):
    """
    Advanced MST-based RFA with configurable folding strategy.
    """

    def __init__(self, nodes, strategy='bottom_up'):
        super().__init__(nodes)
        self.strategy = strategy

    def fold(self):
        """Fold nodes using specified MST strategy."""
        if self.strategy == 'bottom_up':
            return RFAMST.mst_bottom_up_fold(list(self.nodes))
        elif self.strategy == 'sequence':
            return RFAMST.mst(list(self.nodes))
        else:
            # Fallback to basic random folding
            return super().fold()

    def unfold(self, nodes_to_unfold):
        """Unfold using breadth-first approach."""
        return unfold_breadth_first(nodes_to_unfold)
