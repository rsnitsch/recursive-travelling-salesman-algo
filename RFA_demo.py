#!/usr/bin/env python3
"""
Script for executing the recursive-fold-algorithm (RFA) for metric travelling-salesman-problems
and displaying visualizations/benchmarks.

@todo: Implement "animation mode" that allows to observe how the algorithm works step by step.
"""

import argparse
import gc
import logging
import os
import random
import re
import sys
import time

from tabulate import tabulate

from common import Route, generate_random_nodes, load_nodes_from_tsplib_file, tsplib_get_optimal_solution
from RFA import (
    FoldingStrategyBreadthFirst,
    FoldingStrategyOutsideIn,
    FoldingStrategyRandomWithNearestNeighbor,
    UnfoldingStrategyBreadthFirst,
    UnfoldingStrategyBreadthFirstWithLocal2Opt,
)

logger = logging.getLogger(__name__)


def create_option_parser():
    parser = argparse.ArgumentParser(
        description="Calculate and display routes for metric travelling-salesman-problems using the recursive-fold-algorithm."
    )

    # Add options to the OptionParser.
    parser.add_argument("mode", type=str, action="store", help="Either 'demo' or 'benchmark'.")

    parser.add_argument(
        "--folding-strategy",
        type=str,
        default="breadth-first",
        choices=["breadth-first", "random-nn", "outside-in"],
    )

    parser.add_argument(
        "--unfolding-strategy", type=str, default="breadth-first-2opt", choices=["breadth-first", "breadth-first-2opt"]
    )

    DEFAULT_NUMBER_OF_NODES = 100
    parser.add_argument(
        "-n",
        "--nodes",
        type=int,
        action="store",
        dest="number_of_nodes",
        default=DEFAULT_NUMBER_OF_NODES,
        help=("Number of nodes for demo mode (default = %d)" % DEFAULT_NUMBER_OF_NODES),
    )

    DEFAULT_SEED = 0
    parser.add_argument(
        "-s",
        "--seed",
        type=int,
        action="store",
        dest="seed",
        default=DEFAULT_SEED,
        help="Random number generator seed (default = %d)" % DEFAULT_SEED,
    )

    parser.add_argument("--renderer", type=str, default="disabled", choices=["disabled", "turtle"])

    parser.add_argument("--intersection-cleanup", action=argparse.BooleanOptionalAction, default=False)

    parser.add_argument(
        "--tsplib",
        type=str,
        default="a280,berlin52,bier127,ch150,eil51,pla7397,pr76,pr107,pr439,pr1002,rat99,rat783,usa13509",
        help="TSPLIB instances to be executed (comma-separated or 'all') or <N for all instances with at most N nodes.",
    )

    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging output")

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
        from ui import RendererTurtle

        return RendererTurtle()
    elif name == "disabled":
        return None
    else:
        raise ValueError("Unknown renderer: %s" % name)


def main(argv):
    parser = create_option_parser()
    args = parser.parse_args(args=argv[1:])

    logging.basicConfig(format="%(levelname)s | %(message)s", level=logging.DEBUG if args.verbose else logging.INFO)

    if not args.mode in ("demo", "benchmark"):
        parser.error("Ungültiger Modus gewählt. Nur 'demo' oder 'benchmark' erlaubt.")

    if args.number_of_nodes <= 2:
        parser.error("Anzahl der nodes muss größer-gleich 3 sein.")

    logger.info("Folding strategy:   %s", args.folding_strategy)
    logger.info("Unfolding strategy: %s", args.unfolding_strategy)
    logger.info("Seed:               %d", args.seed)

    if args.mode == "demo":
        main_random(
            args.folding_strategy,
            args.unfolding_strategy,
            args.intersection_cleanup,
            args.renderer,
            args.number_of_nodes,
            args.seed,
        )
    elif args.mode == "benchmark":
        main_tsplib(
            args.tsplib,
            args.folding_strategy,
            args.unfolding_strategy,
            args.intersection_cleanup,
            args.renderer,
            args.seed,
        )

    return 0


def main_random(folding_strategy, unfolding_strategy, intersection_cleanup, renderer, number_of_nodes, seed=0):
    # KONFIGURATION:
    """
    Gibt an, wie groß die X- bzw. Y-Koordinaten maximal sein dürfen.
    Die Koordinaten werden dann im Intervall [0, max_size] liegen.

    Empfohlen: 500.
    """
    max_size = 500

    # ENDE DER KONFIGURATION.

    nodes = generate_random_nodes(number_of_nodes, max_size=max_size)
    ceil_2d = False

    # Zur Reproduzierbarkeit.
    random.seed(seed)

    # RFA ausführen.
    folding_strategy_instance = get_folding_strategy_by_name(folding_strategy)
    unfolding_strategy_instance = get_unfolding_strategy_by_name(unfolding_strategy)
    renderer_instance = get_renderer_by_name(renderer)

    logger.debug("Folding...")
    start_time = time.time()
    folded = folding_strategy_instance.fold(nodes, ceil_2d, renderer_instance)
    assert len(folded) <= 3, "Folding did not reduce number of nodes to 3."

    logger.debug("Unfolding...")
    route = Route(unfolding_strategy_instance.unfold(folded, ceil_2d, renderer_instance))
    if intersection_cleanup:
        route = route.intersection_cleanup()
        if renderer_instance:
            renderer_instance.visualize(route)
    end_time = time.time()

    total_costs = route.get_total_costs(ceil_2d)
    runtime = end_time - start_time

    logger.info("Total costs:\t%s", total_costs)
    logger.info("Runtime:\t%.3fs", runtime)
    logger.info("")

    if renderer_instance:
        renderer_instance.wait_until_closed()


def main_tsplib(tsplib: str, folding_strategy, unfolding_strategy, intersection_cleanup, renderer, seed=0):
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
            if intersection_cleanup:
                route = route.intersection_cleanup()
                if renderer_instance:
                    renderer_instance.visualize(route)
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
    sys.exit(main(sys.argv))
