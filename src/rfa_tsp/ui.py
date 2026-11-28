#!/usr/bin/env python3
"""
Visualization base classes, step snapshots, and renderers for RFA.

Copyright (c) 2010-2026 Robert Nitsch
"""

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum

from .common import CoordinateNode, RFANode

logger = logging.getLogger(__name__)


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


def _snapshot_node(node: CoordinateNode) -> NodeSnapshot:
    return NodeSnapshot(x=node.x, y=node.y, depth=getattr(node, "depth", 0))


def _snapshot_nodes(nodes: Iterable[CoordinateNode]) -> tuple[NodeSnapshot, ...]:
    return tuple(_snapshot_node(n) for n in nodes)


class Renderer:
    """Base renderer that records algorithm steps as lightweight snapshots."""

    def __init__(self) -> None:
        self.history: list[StepSnapshot] = []

    def record_init(self, nodes: Iterable[CoordinateNode]) -> None:
        self.history.append(StepSnapshot(phase=Phase.INIT, nodes=_snapshot_nodes(nodes)))

    def record_fold(
        self, active_nodes: Iterable[CoordinateNode], node1: CoordinateNode, node2: CoordinateNode, folded_node: RFANode
    ) -> None:
        self.history.append(
            StepSnapshot(
                phase=Phase.FOLD,
                nodes=_snapshot_nodes(active_nodes),
                fold_sources=(_snapshot_node(node1), _snapshot_node(node2)),
                fold_result=_snapshot_node(folded_node),
            )
        )

    def record_anchor(self, route_nodes: Iterable[CoordinateNode]) -> None:
        self.history.append(StepSnapshot(phase=Phase.ANCHOR, nodes=_snapshot_nodes(route_nodes)))

    def record_unfold(
        self,
        route_nodes: Iterable[CoordinateNode],
        parent_node: RFANode,
        child1: CoordinateNode,
        child2: CoordinateNode,
    ) -> None:
        self.history.append(
            StepSnapshot(
                phase=Phase.UNFOLD,
                nodes=_snapshot_nodes(route_nodes),
                unfold_parent=_snapshot_node(parent_node),
                unfold_children=(_snapshot_node(child1), _snapshot_node(child2)),
            )
        )

    def record_post_process(self, route_nodes: Iterable[CoordinateNode], cost: int | None = None) -> None:
        self.history.append(
            StepSnapshot(
                phase=Phase.POST_PROCESS,
                nodes=_snapshot_nodes(route_nodes),
                cost=cost,
            )
        )

    def wait_until_closed(self) -> None:
        raise NotImplementedError("wait_until_closed() must be implemented in subclasses")
