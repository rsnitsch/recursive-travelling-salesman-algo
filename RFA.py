#!/usr/bin/env python3
"""
Recursive-fold-algorithm (RFA) for metric travelling-salesman-problems.
"""

import heapq
import random
from math import ceil, floor, sqrt

from common import CoordinateNode, Route
from ui import Renderer


class SpatialGrid:
    """
    Dynamic 2D spatial hash grid for exact nearest-neighbor queries in O(1) expected time.
    Automatically rebuilds with coarser cell sizes as nodes are folded away.
    """

    def __init__(self, nodes: list[CoordinateNode]):
        self.count = 0
        self.rebuild_threshold = 0
        self.cell_size = 1.0
        self.inv_cell_size = 1.0
        self.cells: dict[tuple[int, int], list[CoordinateNode]] = {}
        self.node_cell: dict[CoordinateNode, tuple[int, int]] = {}
        if nodes:
            self._build(nodes)

    def _build(self, nodes: list[CoordinateNode]):
        self.cells.clear()
        self.node_cell.clear()
        self.count = len(nodes)
        self.rebuild_threshold = self.count // 2

        min_x = min(n.x for n in nodes)
        max_x = max(n.x for n in nodes)
        min_y = min(n.y for n in nodes)
        max_y = max(n.y for n in nodes)

        width = max(max_x - min_x, 1e-9)
        height = max(max_y - min_y, 1e-9)
        # Target ~1-2 nodes per grid cell
        self.cell_size = max(sqrt((width * height) / max(self.count, 1)), 1e-9)
        self.inv_cell_size = 1.0 / self.cell_size

        for node in nodes:
            self._insert_raw(node)

    def _insert_raw(self, node: CoordinateNode):
        key = (floor(node.x * self.inv_cell_size), floor(node.y * self.inv_cell_size))
        self.node_cell[node] = key
        bucket = self.cells.get(key)
        if bucket is None:
            self.cells[key] = [node]
        else:
            bucket.append(node)

    def add(self, node: CoordinateNode):
        self._insert_raw(node)
        self.count += 1

    def remove(self, node: CoordinateNode):
        key = self.node_cell.pop(node)
        bucket = self.cells[key]
        if len(bucket) == 1:
            del self.cells[key]
        else:
            bucket.remove(node)
        self.count -= 1

        # Rebuild grid when node count halves so cell density stays optimal
        if self.count <= self.rebuild_threshold and self.count >= 64:
            self._build(list(self.node_cell.keys()))

    def get_nearest_neighbor(self, query: CoordinateNode, ceil_2d: bool) -> tuple[CoordinateNode, int]:
        # Direct linear scan when few nodes remain (faster than grid ring traversal)
        if self.count < 64:
            return query.get_nearest_neighbor(list(self.node_cell.keys()), ceil_2d)

        qx, qy = query.x, query.y
        cx = floor(qx * self.inv_cell_size)
        cy = floor(qy * self.inv_cell_size)

        best_node: CoordinateNode | None = None
        best_dist_sq = float("inf")
        max_ring = 1
        ring = 0

        while ring <= max_ring:
            if ring == 0:
                bucket = self.cells.get((cx, cy))
                if bucket:
                    for node in bucket:
                        dx = node.x - qx
                        dy = node.y - qy
                        d_sq = dx * dx + dy * dy
                        if d_sq < best_dist_sq:
                            best_dist_sq = d_sq
                            best_node = node
            else:
                # Top and bottom rows of the ring
                for ix in range(cx - ring, cx + ring + 1):
                    for iy in (cy - ring, cy + ring):
                        bucket = self.cells.get((ix, iy))
                        if bucket:
                            for node in bucket:
                                dx = node.x - qx
                                dy = node.y - qy
                                d_sq = dx * dx + dy * dy
                                if d_sq < best_dist_sq:
                                    best_dist_sq = d_sq
                                    best_node = node

                # Left and right columns (excluding corners already checked above)
                for iy in range(cy - ring + 1, cy + ring):
                    for ix in (cx - ring, cx + ring):
                        bucket = self.cells.get((ix, iy))
                        if bucket:
                            for node in bucket:
                                dx = node.x - qx
                                dy = node.y - qy
                                d_sq = dx * dx + dy * dy
                                if d_sq < best_dist_sq:
                                    best_dist_sq = d_sq
                                    best_node = node

            if best_node is not None:
                # Minimum possible distance to any cell outside `max_ring` is at least
                # (max_ring * cell_size), guaranteeing exact nearest-neighbor optimality
                required_rings = ceil(sqrt(best_dist_sq) * self.inv_cell_size)
                if required_rings < max_ring:
                    max_ring = required_rings
            else:
                # Expand search radius until at least one candidate is found
                max_ring = ring + 1

            ring += 1

        assert best_node is not None
        return best_node, query.get_travel_costs(best_node, ceil_2d)


class RFANode(CoordinateNode):
    def __init__(self, children: tuple[CoordinateNode, CoordinateNode], weighted: bool = False):
        child1, child2 = children
        self.children = children

        if weighted:
            w1 = child1.weight if isinstance(child1, RFANode) else 1
            w2 = child2.weight if isinstance(child2, RFANode) else 1
            self.weight = w1 + w2
            x = (w1 * child1.x + w2 * child2.x) / self.weight
            y = (w1 * child1.y + w2 * child2.y) / self.weight
        else:
            self.weight = 1
            x = (child1.x + child2.x) / 2
            y = (child1.y + child2.y) / 2

        CoordinateNode.__init__(self, x, y)

        d1 = child1.depth if isinstance(child1, RFANode) else 0
        d2 = child2.depth if isinstance(child2, RFANode) else 0
        self.depth = max(d1, d2) + 1


class FoldingStrategy:
    def fold(self, nodes: list[CoordinateNode], ceil_2d: bool, renderer: Renderer | None):
        """Fold nodes using the strategy defined in the subclass."""
        raise NotImplementedError("fold() must be implemented in subclasses")


class FoldingStrategyBreadthFirst(FoldingStrategy):
    def fold(self, nodes: list[CoordinateNode], ceil_2d: bool, renderer: Renderer | None):
        active = list(nodes)
        if renderer:
            renderer.visualize(active)

        grid = SpatialGrid(active)
        by_depth: dict[int, list[CoordinateNode]] = {0: list(active)}
        min_depth = 0

        while grid.count > 3:
            while not by_depth.get(min_depth):
                min_depth += 1

            level_nodes = by_depth[min_depth]
            idx = random.randrange(len(level_nodes))
            node1 = level_nodes[idx]
            level_nodes[idx] = level_nodes[-1]
            level_nodes.pop()

            if node1 not in grid.node_cell:
                continue
            grid.remove(node1)

            node2, _ = grid.get_nearest_neighbor(node1, ceil_2d)
            grid.remove(node2)

            folded = RFANode((node1, node2))
            grid.add(folded)
            by_depth.setdefault(folded.depth, []).append(folded)

            if renderer:
                renderer.visualize(list(grid.node_cell.keys()))

        return list(grid.node_cell.keys())


class FoldingStrategyRandomWithNearestNeighbor(FoldingStrategy):
    """
    Nodes are picked in random order. Each node is folded with its nearest neighbor
    using a dynamic 2D spatial hash grid for fast lookup.
    """

    def fold(self, nodes: list[CoordinateNode], ceil_2d: bool, renderer: Renderer | None):
        active = list(nodes)
        if renderer:
            renderer.visualize(active)

        grid = SpatialGrid(active)
        pos = {node: i for i, node in enumerate(active)}

        def remove_active(node: CoordinateNode):
            idx = pos.pop(node)
            last = active.pop()
            if idx < len(active):
                active[idx] = last
                pos[last] = idx

        while len(active) > 3:
            node1 = random.choice(active)
            remove_active(node1)
            grid.remove(node1)

            node2, _ = grid.get_nearest_neighbor(node1, ceil_2d)
            remove_active(node2)
            grid.remove(node2)

            folded = RFANode((node1, node2))
            pos[folded] = len(active)
            active.append(folded)
            grid.add(folded)

            if renderer:
                renderer.visualize(active)

        return active


class FoldingStrategyOutsideIn(FoldingStrategy):
    """
    Outside-in folding with fixed center point calculated at the beginning,
    accelerated with SpatialGrid and a max-heap for furthest-node selection.
    """

    def fold(self, nodes: list[CoordinateNode], ceil_2d: bool, renderer: Renderer | None):
        active = list(nodes)
        if renderer:
            renderer.visualize(active)

        if len(active) <= 3:
            return active

        # Calculate fixed center point from initial node set
        center_x = sum(node.x for node in active) / len(active)
        center_y = sum(node.y for node in active) / len(active)

        grid = SpatialGrid(active)

        # Max-heap storing (-dist_sq, tie_breaker_id, node) for O(log n) furthest-node lookup
        counter = 0
        heap: list[tuple[float, int, CoordinateNode]] = []
        for node in active:
            dist_sq = (node.x - center_x) ** 2 + (node.y - center_y) ** 2
            heapq.heappush(heap, (-dist_sq, counter, node))
            counter += 1

        while grid.count > 3:
            # Pop furthest still-active node (lazy deletion for already-folded nodes)
            furthest_node: CoordinateNode | None = None
            while heap:
                _, _, candidate = heapq.heappop(heap)
                if candidate in grid.node_cell:
                    furthest_node = candidate
                    break

            if furthest_node is None:
                break

            grid.remove(furthest_node)

            if grid.count == 0:
                break

            # Find nearest neighbor via SpatialGrid
            nearest_neighbor, _ = grid.get_nearest_neighbor(furthest_node, ceil_2d)
            grid.remove(nearest_neighbor)

            # Create folded node
            folded_node = RFANode((furthest_node, nearest_neighbor))
            grid.add(folded_node)

            dist_sq = (folded_node.x - center_x) ** 2 + (folded_node.y - center_y) ** 2
            heapq.heappush(heap, (-dist_sq, counter, folded_node))
            counter += 1

            if renderer:
                renderer.visualize(list(grid.node_cell.keys()))

        return list(grid.node_cell.keys())


class UnfoldingStrategy:
    def unfold(self, nodes_to_unfold: list[RFANode | CoordinateNode], ceil_2d, renderer):
        """Unfold nodes using the strategy defined in the subclass."""
        raise NotImplementedError("unfold() must be implemented in subclasses")


class UnfoldingStrategyBreadthFirst(UnfoldingStrategy):
    """Unfolding strategy that processes nodes in breadth-first manner.

    The list of folded nodes is processed repeatedly. During each iteration,
    only the nodes with the maximum depth are unfolded.
    """

    def __init__(self):
        self.enable_local_2opt = False

    def unfold(self, nodes_to_unfold: list[RFANode | CoordinateNode], ceil_2d, renderer):
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
                current_node = nodes[i]
                if not isinstance(current_node, RFANode):
                    i += 1
                    continue

                if current_node.depth < max_depth:
                    # Only unfold the nodes that are at the maximum depth.
                    i += 1
                    continue

                before = nodes[i - 1] if i > 0 else nodes[len(nodes) - 1]
                after = nodes[i + 1] if i < len(nodes) - 1 else nodes[0]

                node1: CoordinateNode = current_node.children[0]
                node2: CoordinateNode = current_node.children[1]
                route1 = Route([before, node1, node2, after])
                route2 = Route([before, node2, node1, after])

                nodes.remove(current_node)

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

                        a: CoordinateNode = tour[i]
                        b: CoordinateNode = tour[(i + 1) % len(tour)]
                        c: CoordinateNode = tour[j]
                        d: CoordinateNode = tour[(j + 1) % len(tour)]

                        old_cost = a.get_travel_costs(b, ceil_2d) + c.get_travel_costs(d, ceil_2d)
                        new_cost = a.get_travel_costs(c, ceil_2d) + b.get_travel_costs(d, ceil_2d)

                        if new_cost < old_cost:
                            # 2-opt move
                            tour[i + 1 : j + 1] = reversed(tour[i + 1 : j + 1])
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
