#!/usr/bin/env python3
"""
Recursive-fold-algorithm (RFA) for metric travelling-salesman-problems.

Copyright (c) 2010-2026 Robert Nitsch
"""

import heapq
import random
from math import ceil, floor, sqrt

from .common import CoordinateNode
from .ui import Renderer


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
                max_ring = min(max_ring, required_rings)
            else:
                # Expand search radius until at least one candidate is found
                max_ring = ring + 1

            ring += 1

        assert best_node is not None
        return best_node, query.get_travel_costs(best_node, ceil_2d)


class RFANode(CoordinateNode):
    __slots__ = ("children", "depth", "weight")

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
            renderer.record_init(active)

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
                renderer.record_fold(list(grid.node_cell.keys()), node1, node2, folded)

        return list(grid.node_cell.keys())


class FoldingStrategyRandomWithNearestNeighbor(FoldingStrategy):
    """
    Nodes are picked in random order. Each node is folded with its nearest neighbor
    using a dynamic 2D spatial hash grid for fast lookup.
    """

    def fold(self, nodes: list[CoordinateNode], ceil_2d: bool, renderer: Renderer | None):
        active = list(nodes)
        if renderer:
            renderer.record_init(active)

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
                renderer.record_fold(active, node1, node2, folded)

        return active


class FoldingStrategyOutsideIn(FoldingStrategy):
    """
    Outside-in folding with fixed center point calculated at the beginning,
    accelerated with SpatialGrid and a max-heap for furthest-node selection.
    """

    def fold(self, nodes: list[CoordinateNode], ceil_2d: bool, renderer: Renderer | None):
        active = list(nodes)
        if renderer:
            renderer.record_init(active)

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
                renderer.record_fold(list(grid.node_cell.keys()), furthest_node, nearest_neighbor, folded_node)

        return list(grid.node_cell.keys())


class UnfoldingStrategy:
    def unfold(self, nodes_to_unfold: list[RFANode | CoordinateNode], ceil_2d, renderer):
        """Unfold nodes using the strategy defined in the subclass."""
        raise NotImplementedError("unfold() must be implemented in subclasses")


class UnfoldingStrategyBreadthFirst(UnfoldingStrategy):
    """Unfolding strategy that processes nodes in breadth-first manner.

    Uses a doubly-linked representation (nxt/prv dicts) so node replacement
    and local 2-opt window updates run in O(1) instead of O(n) list shifts.
    """

    def __init__(self):
        self.enable_local_2opt = False

    def unfold(self, nodes_to_unfold: list[RFANode | CoordinateNode], ceil_2d, renderer):
        nodes = list(nodes_to_unfold)
        n = len(nodes)
        if n == 0:
            return nodes

        # Circular doubly-linked tour representation: O(1) insert/remove
        nxt: dict[CoordinateNode, CoordinateNode] = {}
        prv: dict[CoordinateNode, CoordinateNode] = {}
        for i in range(n):
            u = nodes[i]
            v = nodes[(i + 1) % n]
            nxt[u] = v
            prv[v] = u

        head = nodes[0]
        tour_len = n

        # Group initial RFANodes by depth
        by_depth: dict[int, list[RFANode]] = {}
        max_depth = 0
        for node in nodes:
            if isinstance(node, RFANode):
                by_depth.setdefault(node.depth, []).append(node)
                max_depth = max(max_depth, node.depth)

        # Localize cost helper to avoid Route object allocations in inner loop
        cost_fn = (
            (lambda a, b: ceil(sqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2)))
            if ceil_2d
            else (lambda a, b: round(sqrt((b.x - a.x) ** 2 + (b.y - a.y) ** 2)))
        )

        def materialize_tour() -> list[CoordinateNode]:
            res = [head]
            curr = nxt[head]
            while curr is not head:
                res.append(curr)
                curr = nxt[curr]
            return res

        if renderer:
            renderer.record_anchor(materialize_tour())

        for depth in range(max_depth, 0, -1):
            level_nodes = by_depth.get(depth)
            if not level_nodes:
                continue

            for current_node in level_nodes:
                # Skip if already unfolded (defensive check)
                if current_node not in nxt:
                    continue

                before = prv[current_node]
                after = nxt[current_node]

                node1: CoordinateNode = current_node.children[0]
                node2: CoordinateNode = current_node.children[1]

                # Compare insertion orders: (before -> node1 -> node2 -> after)
                # vs. (before -> node2 -> node1 -> after).
                # Note: cost(node1, node2) == cost(node2, node1), so we only compare outer edges!
                cost_order_1 = cost_fn(before, node1) + cost_fn(node2, after)
                cost_order_2 = cost_fn(before, node2) + cost_fn(node1, after)

                if cost_order_1 < cost_order_2:
                    first, second = node1, node2
                else:
                    first, second = node2, node1

                # Replace current_node with first -> second in O(1)
                del nxt[current_node]
                del prv[current_node]

                nxt[before] = first
                prv[first] = before
                nxt[first] = second
                prv[second] = first
                nxt[second] = after
                prv[after] = second

                if head is current_node:
                    head = first

                tour_len += 1

                # Enqueue child RFANodes for their respective depth passes
                if isinstance(first, RFANode):
                    by_depth.setdefault(first.depth, []).append(first)
                if isinstance(second, RFANode):
                    by_depth.setdefault(second.depth, []).append(second)

                # Local 2-opt around the inserted nodes in O(radius^2)
                if self.enable_local_2opt and tour_len >= 4:
                    head = self.local_2opt_segment(nxt, prv, head, first, second, tour_len, cost_fn, radius=5)

                if renderer:
                    renderer.record_unfold(materialize_tour(), current_node, first, second)

        return materialize_tour()

    def local_2opt_segment(self, nxt, prv, head, first, second, tour_len, cost_fn, radius=5):
        """
        Perform a local 2-opt in a small neighborhood window around (first, second)
        directly on the doubly-linked tour without O(n) list scans or index() lookups.
        """
        # Walk `radius` steps backward from `first`
        left_steps = min(radius, (tour_len - 2) // 2)
        right_steps = min(radius, tour_len - 2 - left_steps)

        win_start = first
        for _ in range(left_steps):
            win_start = prv[win_start]

        # Extract small local window of nodes into a short list (at most 2*radius + 2 nodes)
        window_len = left_steps + 2 + right_steps
        window = [win_start]
        curr = win_start
        for _ in range(window_len - 1):
            curr = nxt[curr]
            window.append(curr)

        left_anchor = prv[window[0]]
        right_anchor = nxt[window[-1]]

        # Run 2-opt only on edges strictly inside the extracted window
        m = len(window)
        if m < 4:
            return head

        changed = True
        while changed:
            changed = False
            for i in range(m - 3):
                a = window[i]
                b = window[i + 1]
                ab_cost = cost_fn(a, b)
                for j in range(i + 2, m - 1):
                    c = window[j]
                    d = window[j + 1]

                    old_cost = ab_cost + cost_fn(c, d)
                    new_cost = cost_fn(a, c) + cost_fn(b, d)

                    if new_cost < old_cost:
                        window[i + 1 : j + 1] = reversed(window[i + 1 : j + 1])
                        b = window[i + 1]
                        ab_cost = cost_fn(a, b)
                        changed = True

        # Stitch modified window back into doubly-linked tour in O(window_len)
        nxt[left_anchor] = window[0]
        prv[window[0]] = left_anchor
        for k in range(m - 1):
            u = window[k]
            v = window[k + 1]
            nxt[u] = v
            prv[v] = u
        nxt[window[-1]] = right_anchor
        prv[right_anchor] = window[-1]

        return head


class UnfoldingStrategyBreadthFirstWithLocal2Opt(UnfoldingStrategyBreadthFirst):
    """
    Like UnfoldingStrategyBreadthFirst, but after each unfolding step,
    a local 2-opt optimization around the inserted nodes is performed.
    """

    def __init__(self):
        super().__init__()
        self.enable_local_2opt = True
