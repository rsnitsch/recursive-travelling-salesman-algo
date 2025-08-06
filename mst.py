#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MST implementation for RFA folding strategy using scipy.sparse.csgraph.
"""
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import minimum_spanning_tree
from collections import defaultdict


class MSTNode:
    """
    Node representation for MST-based folding.
    Contains original node and its children in the MST.
    """

    def __init__(self, original_node, index):
        self.original = original_node
        self.index = index  # Index in the original node list
        self.children = []
        self.parent = None
        self.x = original_node.x
        self.y = original_node.y

    def add_child(self, child_node):
        """Add a child to this MST node."""
        self.children.append(child_node)
        child_node.parent = self

    def get_travel_costs(self, other_node):
        """Delegate to original node for distance calculation."""
        return self.original.get_travel_costs(other_node.original)

    def is_leaf(self):
        """Check if this node is a leaf in the MST."""
        return len(self.children) == 0

    def __str__(self):
        return f"MST({self.original})"


def build_distance_matrix(nodes):
    """
    Build distance matrix for scipy MST computation.
    Returns sparse CSR matrix.
    """
    n = len(nodes)

    # Create dense matrix first (easier to fill)
    distances = np.zeros((n, n))

    for i in range(n):
        for j in range(i + 1, n):
            dist = nodes[i].get_travel_costs(nodes[j])
            distances[i, j] = dist
            distances[j, i] = dist  # Symmetric matrix

    # Convert to sparse matrix
    return csr_matrix(distances)


def build_mst_tree_scipy(nodes):
    """
    Build MST using scipy and return as tree structure.
    Returns the root of the MST tree.
    """
    if not nodes:
        return None

    if len(nodes) == 1:
        return MSTNode(nodes[0], 0)

    # Build distance matrix
    distance_matrix = build_distance_matrix(nodes)

    # Compute MST using scipy
    mst_sparse = minimum_spanning_tree(distance_matrix)

    # Convert sparse MST to adjacency list
    mst_coo = mst_sparse.tocoo()  # Convert to coordinate format for easy iteration
    adjacency = defaultdict(list)

    for i, j, weight in zip(mst_coo.row, mst_coo.col, mst_coo.data):
        adjacency[i].append(j)
        adjacency[j].append(i)  # Undirected graph

    # Create MST nodes
    mst_nodes = [MSTNode(nodes[i], i) for i in range(len(nodes))]

    # Build tree structure using DFS from node 0 as root
    visited = set()

    def build_tree_dfs(node_idx, parent_idx=None):
        """Build tree structure via DFS."""
        if node_idx in visited:
            return

        visited.add(node_idx)
        current_node = mst_nodes[node_idx]

        # Add children (all neighbors except parent)
        for neighbor_idx in adjacency[node_idx]:
            if neighbor_idx != parent_idx and neighbor_idx not in visited:
                child_node = mst_nodes[neighbor_idx]
                current_node.add_child(child_node)
                build_tree_dfs(neighbor_idx, node_idx)

    # Start DFS from node 0 as root
    build_tree_dfs(0)

    return mst_nodes[0]  # Return root


def build_mst_tree(nodes):
    """
    Main interface function - delegates to scipy implementation.
    """
    return build_mst_tree_scipy(nodes)


def mst_fold_sequence(root_node):
    """
    Generate folding sequence based on MST structure.
    Returns list of (parent, child) pairs to fold, starting from leaves.
    """
    if not root_node:
        return []

    fold_sequence = []

    def collect_foldable_pairs(node):
        """Recursively collect leaf nodes that can be folded with their parents."""
        # First, process all children
        for child in node.children[:]:  # Copy list as we might modify it
            collect_foldable_pairs(child)

        # If this node has exactly one child and that child is a leaf, fold them
        if len(node.children) == 1 and node.children[0].is_leaf():
            child = node.children[0]
            fold_sequence.append((node.original, child.original))
            # Remove child after folding
            node.children.remove(child)

        # If this node has two children and both are leaves, fold them
        elif len(node.children) == 2 and all(child.is_leaf() for child in node.children):
            child1, child2 = node.children
            fold_sequence.append((child1.original, child2.original))
            # Remove both children after folding
            node.children.clear()

    # Continue until we have few enough nodes
    while count_total_nodes(root_node) > 3:
        old_sequence_length = len(fold_sequence)
        collect_foldable_pairs(root_node)

        # Safety break if no more folding possible
        if len(fold_sequence) == old_sequence_length:
            break

    return fold_sequence


def count_total_nodes(node):
    """Count total nodes in the tree rooted at given node."""
    if not node:
        return 0
    count = 1
    for child in node.children:
        count += count_total_nodes(child)
    return count


def find_foldable_leaf(node):
    """Find a leaf node that can be folded with its parent."""
    if node.is_leaf() and node.parent:
        return (node.parent, node)

    for child in node.children:
        result = find_foldable_leaf(child)
        if result:
            return result

    return None
