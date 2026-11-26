#!/usr/bin/env python3
"""
Visualization base classes, step snapshots, and renderers for RFA.

Copyright (c) 2010-2026 Robert Nitsch
"""

import turtle
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum


class Phase(StrEnum):
    INIT = "init"
    FOLD = "fold"
    ANCHOR = "anchor"
    UNFOLD = "unfold"
    POST_PROCESS = "post_process"


@dataclass(frozen=True, slots=True)
class NodeSnapshot:
    x: float
    y: float
    depth: int = 0


@dataclass(frozen=True, slots=True)
class StepSnapshot:
    phase: Phase
    nodes: tuple[NodeSnapshot, ...]
    fold_sources: tuple[NodeSnapshot, NodeSnapshot] | None = None
    fold_result: NodeSnapshot | None = None
    unfold_parent: NodeSnapshot | None = None
    unfold_children: tuple[NodeSnapshot, NodeSnapshot] | None = None
    cost: int | None = None


def _snapshot_node(node) -> NodeSnapshot:
    return NodeSnapshot(x=node.x, y=node.y, depth=getattr(node, "depth", 0))


def _snapshot_nodes(nodes: Iterable) -> tuple[NodeSnapshot, ...]:
    return tuple(_snapshot_node(n) for n in nodes)


class Renderer:
    """Base renderer that records algorithm steps as lightweight snapshots."""

    def __init__(self) -> None:
        self.history: list[StepSnapshot] = []

    def record_init(self, nodes: Iterable) -> None:
        self.history.append(StepSnapshot(phase=Phase.INIT, nodes=_snapshot_nodes(nodes)))

    def record_fold(self, active_nodes: Iterable, node1, node2, folded_node) -> None:
        self.history.append(
            StepSnapshot(
                phase=Phase.FOLD,
                nodes=_snapshot_nodes(active_nodes),
                fold_sources=(_snapshot_node(node1), _snapshot_node(node2)),
                fold_result=_snapshot_node(folded_node),
            )
        )

    def record_anchor(self, route_nodes: Iterable) -> None:
        self.history.append(StepSnapshot(phase=Phase.ANCHOR, nodes=_snapshot_nodes(route_nodes)))

    def record_unfold(self, route_nodes: Iterable, parent_node, child1, child2) -> None:
        self.history.append(
            StepSnapshot(
                phase=Phase.UNFOLD,
                nodes=_snapshot_nodes(route_nodes),
                unfold_parent=_snapshot_node(parent_node),
                unfold_children=(_snapshot_node(child1), _snapshot_node(child2)),
            )
        )

    def record_post_process(self, route_nodes: Iterable, cost: int | None = None) -> None:
        self.history.append(
            StepSnapshot(
                phase=Phase.POST_PROCESS,
                nodes=_snapshot_nodes(route_nodes),
                cost=cost,
            )
        )

    def wait_until_closed(self) -> None:
        raise NotImplementedError("wait_until_closed() must be implemented in subclasses")


class RendererTurtle(Renderer):
    def __init__(self, scale=1.5):
        super().__init__()
        self.scale = scale
        self.current_idx = 0
        self.screen = turtle.Screen()
        self.screen.tracer(0, 0)
        self.t = turtle.Turtle(visible=False)
        self.t.speed("fastest")
        self._coords_setup = False

    def _setup_coords(self, nodes: tuple[NodeSnapshot, ...]):
        min_x = min(node.x for node in nodes)
        max_x = max(node.x for node in nodes)
        min_y = min(node.y for node in nodes)
        max_y = max(node.y for node in nodes)
        data_width = max_x - min_x or 1
        data_height = max_y - min_y or 1
        data_aspect = data_width / float(data_height)
        MAX_DISPLAY_DIMENSION = 500
        display_padding = MAX_DISPLAY_DIMENSION * 0.1
        if data_width > data_height:
            display_width = MAX_DISPLAY_DIMENSION
            display_height = display_width / data_aspect
        else:
            display_height = MAX_DISPLAY_DIMENSION
            display_width = display_height * data_aspect
        w = display_width + 2 * display_padding
        h = display_height + 2 * display_padding

        self.screen.setup(width=w * self.scale, height=h * self.scale)
        self.offset_x = min_x
        self.offset_y = min_y
        self.data_width = data_width
        self.data_height = data_height
        self.display_width = display_width
        self.display_height = display_height
        self._coords_setup = True

    def _tx(self, x):
        return ((x - self.offset_x) / self.data_width * self.display_width - self.display_width / 2.0) * self.scale

    def _ty(self, y):
        return ((y - self.offset_y) / self.data_height * self.display_height - self.display_height / 2.0) * self.scale

    def draw_route(self, idx: int):
        if idx < 0 or idx >= len(self.history):
            raise IndexError("Index out of range for step history.")

        step = self.history[idx]
        route = step.nodes
        title = f"Step {self.current_idx + 1}/{len(self.history)} [{step.phase.value}] - Nodes: {len(route)}"
        self.screen.title(title)

        if not self._coords_setup:
            self._setup_coords(self.history[0].nodes)

        self.t.clear()
        self.t.penup()
        self.t.goto(self._tx(route[0].x), self._ty(route[0].y))
        self.t.pendown()
        for node in route[1:]:
            self.t.goto(self._tx(node.x), self._ty(node.y))
            self.t.dot(4)
        self.t.goto(self._tx(route[0].x), self._ty(route[0].y))
        self.t.dot(8)
        self.screen.update()

    def prev(self):
        self.current_idx = (self.current_idx - 1) % len(self.history)
        self.draw_route(self.current_idx)

    def next(self):
        self.current_idx = (self.current_idx + 1) % len(self.history)
        self.draw_route(self.current_idx)

    def setup_keybindings(self):
        self.screen.listen()
        self.screen.onkey(self.prev, "Left")
        self.screen.onkey(self.next, "Right")

    def wait_until_closed(self):
        self.current_idx = len(self.history) - 1
        self.draw_route(self.current_idx)
        self.setup_keybindings()
        self.screen.mainloop()
