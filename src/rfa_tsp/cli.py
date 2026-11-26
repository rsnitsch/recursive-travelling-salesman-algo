#!/usr/bin/env python3
"""
Script for executing the recursive-fold-algorithm (RFA) for metric travelling-salesman-problems
and displaying visualizations/benchmarks.

@todo: Implement "animation mode" that allows to observe how the algorithm works step by step.

Copyright (c) 2010-2026 Robert Nitsch
"""

import argparse
import gc
import logging
import os
import random
import re
import sys
import time
from pathlib import Path

from tabulate import tabulate

from .common import Route, generate_random_nodes, load_nodes_from_tsplib_file, tsplib_get_optimal_solution
from .rfa import (
    FoldingStrategyBreadthFirst,
    FoldingStrategyOutsideIn,
    FoldingStrategyRandomWithNearestNeighbor,
    UnfoldingStrategyBreadthFirst,
    UnfoldingStrategyBreadthFirstWithLocal2Opt,
)

logger = logging.getLogger(__name__)


def create_option_parser():
    # Shared arguments available to all subcommands.
    common_parser = argparse.ArgumentParser(add_help=False)

    common_parser.add_argument(
        "--folding-strategy",
        type=str,
        default="breadth-first",
        choices=["breadth-first", "random-nn", "outside-in"],
    )

    common_parser.add_argument(
        "--unfolding-strategy",
        type=str,
        default="breadth-first-2opt",
        choices=["breadth-first", "breadth-first-2opt"],
    )

    DEFAULT_SEED = 0
    common_parser.add_argument(
        "-s",
        "--seed",
        type=int,
        action="store",
        dest="seed",
        default=DEFAULT_SEED,
        help="Random number generator seed (default = %d)" % DEFAULT_SEED,
    )

    common_parser.add_argument(
        "--post-uncross",
        action="store_true",
        default=False,
        help="Remove intersecting edges from the final route via 2-opt moves (default: off)",
    )

    common_parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging output")

    # Main parser with subcommands.
    parser = argparse.ArgumentParser(
        description="Calculate and display routes for metric travelling-salesman-problems using the recursive-fold-algorithm."
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)

    # 'demo' subcommand.
    demo_parser = subparsers.add_parser(
        "demo",
        parents=[common_parser],
        help="Run RFA on randomly generated nodes and optionally visualize the result.",
    )
    DEFAULT_NUMBER_OF_NODES = 100
    demo_parser.add_argument(
        "-n",
        "--nodes",
        type=int,
        action="store",
        dest="number_of_nodes",
        default=DEFAULT_NUMBER_OF_NODES,
        help=("Number of nodes (default = %d)" % DEFAULT_NUMBER_OF_NODES),
    )
    demo_parser.add_argument("--renderer", type=str, default="disabled", choices=["disabled", "turtle", "matplotlib"])
    demo_parser.add_argument(
        "--export",
        type=Path,
        default=None,
        help="Export animation to a file (.gif, .mp4, .mov, .webm).",
    )
    demo_parser.add_argument(
        "--export-fps",
        type=int,
        default=8,
        help="Frames per second for exported animation (default = 8).",
    )

    # 'benchmark' subcommand.
    benchmark_parser = subparsers.add_parser(
        "benchmark",
        parents=[common_parser],
        help="Run RFA benchmark on TSPLIB instances.",
    )
    benchmark_parser.add_argument(
        "--tsplib",
        type=str,
        default="a280,berlin52,bier127,ch150,eil51,pla7397,pr76,pr107,pr439,pr1002,rat99,rat783,usa13509",
        help="TSPLIB instances to be executed (comma-separated or 'all') or <N for all instances with at most N nodes.",
    )
    benchmark_parser.add_argument("--renderer", type=str, default="disabled", choices=["disabled", "turtle"])

    return parser


def get_folding_strategy_by_name(name):
    if name == "breadth-first":
        return FoldingStrategyBreadthFirst()
    elif name == "random-nn":
        return FoldingStrategyRandomWithNearestNeighbor()
    elif name == "outside-in":
        return FoldingStrategyOutsideIn()
    else:
        raise ValueError("Unknown folding strategy: %s" % name)


def get_unfolding_strategy_by_name(name):
    if name == "breadth-first":
        return UnfoldingStrategyBreadthFirst()
    elif name == "breadth-first-2opt":
        return UnfoldingStrategyBreadthFirstWithLocal2Opt()
    else:
        raise ValueError("Unknown unfolding strategy: %s" % name)


def get_renderer_by_name(name):
    if name == "turtle":
        from .ui import RendererTurtle

        return RendererTurtle()
    elif name == "matplotlib":
        from .ui import RendererMatplotlib

        return RendererMatplotlib()
    elif name == "disabled":
        return None
    else:
        raise ValueError("Unknown renderer: %s" % name)


def main():
    parser = create_option_parser()
    args = parser.parse_args()

    logging.basicConfig(format="%(levelname)s | %(message)s", level=logging.DEBUG if args.verbose else logging.INFO)

    logger.info("Folding strategy:   %s", args.folding_strategy)
    logger.info("Unfolding strategy: %s", args.unfolding_strategy)
    logger.info("Seed:               %d", args.seed)

    if args.mode == "demo":
        if args.number_of_nodes <= 2:
            parser.error("Anzahl der nodes muss größer-gleich 3 sein.")

        main_random(
            args.folding_strategy,
            args.unfolding_strategy,
            args.post_uncross,
            args.renderer,
            args.number_of_nodes,
            args.seed,
            export_path=args.export,
            export_fps=args.export_fps,
        )
    elif args.mode == "benchmark":
        main_tsplib(
            args.tsplib,
            args.folding_strategy,
            args.unfolding_strategy,
            args.post_uncross,
            args.renderer,
            args.seed,
        )

    return 0


def main_random(
    folding_strategy,
    unfolding_strategy,
    post_uncross,
    renderer,
    number_of_nodes,
    seed=0,
    export_path: Path | None = None,
    export_fps: int = 8,
):
    max_size = 500
    nodes = generate_random_nodes(number_of_nodes, max_size=max_size)
    ceil_2d = False

    random.seed(seed)

    folding_strategy_instance = get_folding_strategy_by_name(folding_strategy)
    unfolding_strategy_instance = get_unfolding_strategy_by_name(unfolding_strategy)

    # Use matplotlib renderer automatically if export is requested without an explicit interactive renderer
    show_window = renderer != "disabled"
    if export_path is not None and renderer == "disabled":
        renderer_instance = get_renderer_by_name("matplotlib")
    else:
        renderer_instance = get_renderer_by_name(renderer)

    logger.debug("Folding...")
    start_time = time.time()
    folded = folding_strategy_instance.fold(nodes, ceil_2d, renderer_instance)
    assert len(folded) <= 3, "Folding did not reduce number of nodes to 3."

    logger.debug("Unfolding...")
    route = Route(unfolding_strategy_instance.unfold(folded, ceil_2d, renderer_instance))
    if post_uncross:
        route = route.intersection_cleanup()
        if renderer_instance:
            renderer_instance.record_post_process(route, cost=route.get_total_costs(ceil_2d))
    end_time = time.time()

    total_costs = route.get_total_costs(ceil_2d)
    runtime = end_time - start_time

    logger.info("Total costs:\t%s", total_costs)
    logger.info("Runtime:\t%.3fs", runtime)
    logger.info("")

    if export_path is not None:
        if hasattr(renderer_instance, "export"):
            renderer_instance.export(export_path, fps=export_fps)
        else:
            logger.error("Selected renderer '%s' does not support animation export.", renderer)

    if show_window and renderer_instance:
        renderer_instance.wait_until_closed()


def main_tsplib(tsplib: str, folding_strategy, unfolding_strategy, post_uncross, renderer, seed=0):
    # Ordner mit den TSPLIB-Instanzen (in entpackter Form)
    tsplib_folder = "./TSPLIB"

    regexp_maxnodes_spec = re.compile("<([0-9]+)")

    available_tsplib_instances = [f[:-4] for f in os.listdir(tsplib_folder) if f.endswith(".tsp")]
    logger.debug("available_tsplib_instances: %s", available_tsplib_instances)

    if tsplib == "all":
        tsplib = ",".join(available_tsplib_instances)
    else:
        maxnodes_spec_match = regexp_maxnodes_spec.match(tsplib)
        logger.debug("maxnodes_spec_match: %s", maxnodes_spec_match)
        if maxnodes_spec_match:
            max_requested_nodes = int(maxnodes_spec_match.group(1))
            logger.debug("max_requested_nodes: %d", max_requested_nodes)

            regexp_nodes = re.compile("[a-z]+([0-9]+)")
            selected_tsplib_instances = []
            for available_tsplib_instance in available_tsplib_instances:
                m = regexp_nodes.match(available_tsplib_instance)
                if m:
                    nodes = int(m.group(1))
                    if nodes <= max_requested_nodes:
                        selected_tsplib_instances.append(available_tsplib_instance)

            if not selected_tsplib_instances:
                logger.error("Selector did not match any TSPLIB instances")
                return

            tsplib = ",".join(selected_tsplib_instances)

    if not tsplib:
        logger.error("No TSPLIB instance selected")
        return

    logger.info("Running benchmark for TSPLIB instances: %s" % tsplib)

    # Zeilen für Ergebnis-Tabelle sammeln.
    rows = []

    # Anwenden des RFA auf die angegebenen TSPLIB-Instanzen.
    try:
        for tspi in tsplib.split(","):
            logger.info("Processing TSPLIB instance %s...", tspi)
            # Zur Reproduzierbarkeit.
            random.seed(seed)

            nodes, ceil_2d = load_nodes_from_tsplib_file(os.path.join(tsplib_folder, "%s.tsp" % tspi))

            folding_strategy_instance = get_folding_strategy_by_name(folding_strategy)
            unfolding_strategy_instance = get_unfolding_strategy_by_name(unfolding_strategy)
            renderer_instance = get_renderer_by_name(renderer)

            logger.debug("Folding...")
            start_time = time.time()
            folded = folding_strategy_instance.fold(nodes, ceil_2d, renderer_instance)
            assert len(folded) <= 3, "Folding did not reduce number of nodes to 3."

            logger.debug("Unfolding...")
            route = Route(unfolding_strategy_instance.unfold(folded, ceil_2d, renderer_instance))
            if post_uncross:
                route = route.intersection_cleanup()
                if renderer_instance:
                    renderer_instance.record_post_process(route, cost=route.get_total_costs(ceil_2d))
            end_time = time.time()
            gc.collect()

            total_costs = route.get_total_costs(ceil_2d)
            runtime = end_time - start_time

            optimal_costs = tsplib_get_optimal_solution(tspi)
            factor = round(float(total_costs) / optimal_costs * 100, 2)

            rows.append([tspi, optimal_costs, total_costs, "%.2f%%" % factor, "%.3fs" % runtime])

            logger.info("  Result: Total cost = %-10s | Runtime = %.3fs", total_costs, runtime)

            if renderer_instance:
                renderer_instance.wait_until_closed()
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received, stopping benchmark.")
        logger.info("")

    # Ergebnis-Tabelle ausgeben.
    headers = ["Instance", "Costs of optimal route", "Costs of RFA route", "Cost factor", "Runtime"]
    logger.info("\n" + tabulate(rows, headers=headers))


if __name__ == "__main__":
    sys.exit(main())
