#!/usr/bin/env python3
"""
CLI for executing, visualizing, and exporting the recursive-fold-algorithm (RFA)
on a single metric travelling-salesman-problem (TSP) instance.

Copyright (c) 2010-2026 Robert Nitsch
"""

import argparse
import logging
import random
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from .common import Route, generate_random_nodes, load_nodes_from_tsplib_file, optimal_solutions
from .rfa import (
    FoldingStrategy,
    FoldingStrategyBreadthFirst,
    FoldingStrategyOutsideIn,
    FoldingStrategyRandomWithNearestNeighbor,
    UnfoldingStrategy,
    UnfoldingStrategyBreadthFirst,
    UnfoldingStrategyBreadthFirstWithLocal2Opt,
)

logger = logging.getLogger(__name__)

FOLDING_STRATEGIES: dict[str, type[FoldingStrategy]] = {
    "breadth-first": FoldingStrategyBreadthFirst,
    "random-nn": FoldingStrategyRandomWithNearestNeighbor,
    "outside-in": FoldingStrategyOutsideIn,
}

UNFOLDING_STRATEGIES: dict[str, type[UnfoldingStrategy]] = {
    "breadth-first": UnfoldingStrategyBreadthFirst,
    "breadth-first-2opt": UnfoldingStrategyBreadthFirstWithLocal2Opt,
}


def create_argument_parser() -> argparse.ArgumentParser:
    def parse_export_fps(value: str) -> tuple[float, float]:
        """Parse either a single FPS value ('8') or a min-max range ('2-15')."""
        if "-" in value:
            parts = value.split("-", maxsplit=1)
            try:
                min_fps = float(parts[0])
                max_fps = float(parts[1])
            except ValueError as exc:
                raise argparse.ArgumentTypeError(f"Invalid FPS range '{value}'. Expected '<min>-<max>'.") from exc
            if min_fps <= 0 or max_fps < min_fps:
                raise argparse.ArgumentTypeError(f"Invalid FPS range '{value}'. Must satisfy 0 < min <= max.")
            return (min_fps, max_fps)

        try:
            fps = float(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(
                f"Invalid FPS value '{value}'. Expected a number or '<min>-<max>'."
            ) from exc
        if fps <= 0:
            raise argparse.ArgumentTypeError("FPS must be greater than 0.")
        return (fps, fps)

    parser = argparse.ArgumentParser(
        description="Compute an approximate route for a single TSP instance using the recursive-fold-algorithm (RFA)."
    )

    parser.add_argument(
        "instance",
        type=str,
        help=(
            "Problem instance to approximate: 'random[:<seed>]' (default seed: 'default') "
            "or 'tsplib:<name>' (e.g. 'tsplib:berlin52')."
        ),
    )
    parser.add_argument(
        "-n",
        "--nodes",
        type=int,
        dest="number_of_nodes",
        default=100,
        help="Number of nodes when instance is 'random[:<seed>]' (default = 100).",
    )
    parser.add_argument(
        "--tsplib-dir",
        type=Path,
        default=Path("TSPLIB"),
        help="Directory containing unpacked TSPLIB .tsp files (default: ./TSPLIB).",
    )
    parser.add_argument(
        "--folding-strategy",
        type=str,
        default="breadth-first",
        choices=list(FOLDING_STRATEGIES),
    )
    parser.add_argument(
        "--unfolding-strategy",
        type=str,
        default="breadth-first-2opt",
        choices=list(UNFOLDING_STRATEGIES),
    )
    parser.add_argument(
        "-s",
        "--seed",
        type=int,
        default=0,
        help="Random number generator seed for the RFA algorithm (default = 0).",
    )
    parser.add_argument(
        "--post-uncross",
        action="store_true",
        default=False,
        help="Remove intersecting edges from the final route via 2-opt moves (default: off).",
    )
    parser.add_argument(
        "--renderer",
        type=str,
        default="disabled",
        choices=["disabled", "turtle", "matplotlib"],
        help="Interactive visualization backend (default: disabled).",
    )
    parser.add_argument(
        "--export",
        type=Path,
        default=None,
        help="Export animation (.gif, .mp4, .mov, .webm) or individual step frames (.png, .svg).",
    )
    parser.add_argument(
        "--export-fps",
        type=parse_export_fps,
        default=(8.0, 8.0),
        help="FPS for exported animation: single value (e.g. '8') or 'min-max' range slowing down toward the recursion anchor (default = 8).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging output.",
    )

    return parser


def get_renderer_by_name(name: str):
    if name == "turtle":
        from .ui import RendererTurtle

        return RendererTurtle()
    if name == "matplotlib":
        from .ui import RendererMatplotlib

        return RendererMatplotlib()
    if name == "disabled":
        return None
    raise ValueError(f"Unknown renderer: {name}")


def load_instance(instance_spec: str, number_of_nodes: int, tsplib_dir: Path):
    """Load nodes for either 'random[:<seed>]' or 'tsplib:<name>'."""
    if instance_spec == "random" or instance_spec.startswith("random:"):
        if number_of_nodes < 3:
            raise ValueError("Number of nodes must be at least 3.")
        if instance_spec == "random":
            node_seed = "default"
        else:
            node_seed = instance_spec.removeprefix("random:").strip()
            if not node_seed:
                raise ValueError("Missing seed after 'random:'.")
        nodes = generate_random_nodes(number_of_nodes, seed=node_seed, max_size=500)
        return nodes, False, None

    if instance_spec.startswith("tsplib:"):
        tspi = instance_spec.removeprefix("tsplib:").strip()
        if not tspi:
            raise ValueError("Missing TSPLIB instance name after 'tsplib:'.")
        tsp_path = tsplib_dir / f"{tspi}.tsp"
        if not tsp_path.is_file():
            raise FileNotFoundError(f"TSPLIB file not found: {tsp_path}")
        nodes, ceil_2d = load_nodes_from_tsplib_file(tsp_path)
        return nodes, ceil_2d, tspi

    raise ValueError(f"Invalid instance '{instance_spec}'. Expected 'random[:<seed>]' or 'tsplib:<name>'.")


def main(argv: Sequence[str] | None = None) -> int:
    parser = create_argument_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        format="%(levelname)s | %(message)s",
        level=logging.DEBUG if args.verbose else logging.INFO,
    )

    try:
        nodes, ceil_2d, tspi = load_instance(args.instance, args.number_of_nodes, args.tsplib_dir)
    except (ValueError, FileNotFoundError) as exc:
        logger.error("%s", exc)
        return 1

    logger.info("Instance:           %s (%d nodes)", args.instance, len(nodes))
    logger.info("Folding strategy:   %s", args.folding_strategy)
    logger.info("Unfolding strategy: %s", args.unfolding_strategy)
    logger.info("Post-uncross:       %s", args.post_uncross)
    logger.info("Seed:               %d", args.seed)

    # Seed global RNG for reproducible RFA folding strategies
    random.seed(args.seed)

    folding_strategy = FOLDING_STRATEGIES[args.folding_strategy]()
    unfolding_strategy = UNFOLDING_STRATEGIES[args.unfolding_strategy]()

    # Automatically use matplotlib when export is requested without an interactive renderer
    show_window = args.renderer != "disabled"
    if args.export is not None and args.renderer == "disabled":
        renderer_instance = get_renderer_by_name("matplotlib")
    else:
        renderer_instance = get_renderer_by_name(args.renderer)

    logger.debug("Folding...")
    start_time = time.perf_counter()
    folded = folding_strategy.fold(nodes, ceil_2d, renderer_instance)
    assert len(folded) <= 3, "Folding did not reduce number of nodes to 3."

    logger.debug("Unfolding...")
    route = Route(unfolding_strategy.unfold(folded, ceil_2d, renderer_instance))
    if args.post_uncross:
        logger.debug("Running post-uncross...")
        route = route.intersection_cleanup()
        if renderer_instance:
            renderer_instance.record_post_process(route, cost=route.get_total_costs(ceil_2d))
    runtime = time.perf_counter() - start_time

    total_costs = route.get_total_costs(ceil_2d)
    logger.info("Total length:       %s", total_costs)
    if tspi is not None and tspi in optimal_solutions:
        optimal_costs = optimal_solutions[tspi]
        overhead_pct = (float(total_costs) / optimal_costs - 1) * 100.0
        logger.info("Optimal route:      %s (overhead of RFA route: +%.2f%%)", optimal_costs, overhead_pct)
    logger.info("Runtime:            %.3fs", runtime)

    if args.export is not None:
        if hasattr(renderer_instance, "export"):
            renderer_instance.export(args.export, fps=args.export_fps)
        else:
            logger.error("Selected renderer '%s' does not support animation export.", args.renderer)

    if show_window and renderer_instance:
        renderer_instance.wait_until_closed()

    return 0


if __name__ == "__main__":
    sys.exit(main())
