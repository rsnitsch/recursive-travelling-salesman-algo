#!/usr/bin/env python3
"""
Batch benchmark runner for the recursive-fold-algorithm (RFA) on TSPLIB95 instances.

Copyright (c) 2010-2026 Robert Nitsch
"""

import argparse
import gc
import logging
import random
import re
import statistics
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from tabulate import tabulate

from .common import Route, load_nodes_from_tsplib_file, tsplib_get_optimal_solution
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
    parser = argparse.ArgumentParser(
        description="Run RFA benchmarks across multiple TSPLIB95 instances and report summary statistics."
    )

    parser.add_argument(
        "--tsplib",
        type=str,
        default="all",
        help="TSPLIB instances to run (comma-separated, 'all', or '<N' for instances with at most N nodes).",
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
        help="default: breadth-first",
    )
    parser.add_argument(
        "--unfolding-strategy",
        type=str,
        default="breadth-first-2opt",
        choices=list(UNFOLDING_STRATEGIES),
        help="default: breadth-first-2opt",
    )
    parser.add_argument(
        "-s",
        "--seed",
        type=int,
        default=0,
        help="Random number generator seed (default = 0).",
    )
    parser.add_argument(
        "--post-uncross",
        action="store_true",
        default=False,
        help="Remove intersecting edges from the final route via 2-opt moves (default: off).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging output.",
    )

    return parser


def resolve_tsplib_instances(selector: str, tsplib_dir: Path) -> list[str]:
    """Resolve a TSPLIB selector ('all', '<N', or comma-separated names) to a sorted list of instance names."""
    if not tsplib_dir.is_dir():
        raise FileNotFoundError(f"TSPLIB directory not found: {tsplib_dir}")

    available = sorted(p.stem for p in tsplib_dir.glob("*.tsp"))
    logger.debug("Available TSPLIB instances (%d): %s", len(available), available)

    if selector == "all":
        return available

    max_nodes_match = re.fullmatch(r"<([0-9]+)", selector.strip())
    if max_nodes_match:
        max_requested_nodes = int(max_nodes_match.group(1))
        logger.debug("Filtering TSPLIB instances with at most %d nodes", max_requested_nodes)

        # Match trailing node count (handles mixed-case names like kroA100)
        node_count_re = re.compile(r"^[a-zA-Z]+([0-9]+)$")
        selected = []
        for name in available:
            match = node_count_re.match(name)
            if match and int(match.group(1)) <= max_requested_nodes:
                selected.append(name)
        return selected

    return [item.strip() for item in selector.split(",") if item.strip()]


def run_benchmark(
    instances: list[str],
    tsplib_dir: Path,
    folding_strategy_name: str,
    unfolding_strategy_name: str,
    post_uncross: bool,
    seed: int,
) -> int:
    if not instances:
        logger.error("No TSPLIB instances selected.")
        return 1

    logger.info("Folding strategy:   %s", folding_strategy_name)
    logger.info("Unfolding strategy: %s", unfolding_strategy_name)
    logger.info("Post-uncross:       %s", post_uncross)
    logger.info("Seed:               %d", seed)
    logger.info("Running benchmark for %d TSPLIB instance(s): %s", len(instances), ", ".join(instances))

    rows: list[list[object]] = []
    factors: list[float] = []
    runtimes: list[float] = []

    try:
        for tspi in instances:
            tsp_path = tsplib_dir / f"{tspi}.tsp"
            if not tsp_path.is_file():
                logger.error("TSPLIB file not found: %s", tsp_path)
                return 1

            logger.info("Processing TSPLIB instance %s...", tspi)
            random.seed(seed)

            nodes, ceil_2d = load_nodes_from_tsplib_file(tsp_path)
            folding_strategy = FOLDING_STRATEGIES[folding_strategy_name]()
            unfolding_strategy = UNFOLDING_STRATEGIES[unfolding_strategy_name]()

            logger.debug("Folding %d nodes...", len(nodes))
            start_time = time.perf_counter()
            folded = folding_strategy.fold(nodes, ceil_2d, renderer=None)
            assert len(folded) <= 3, "Folding did not reduce number of nodes to 3."

            logger.debug("Unfolding...")
            route = Route(unfolding_strategy.unfold(folded, ceil_2d, renderer=None))
            if post_uncross:
                logger.debug("Running post-uncross...")
                route = route.intersection_cleanup()
            runtime = time.perf_counter() - start_time
            gc.collect()

            total_costs = route.get_total_costs(ceil_2d)
            optimal_costs = tsplib_get_optimal_solution(tspi)
            factor_pct = float(total_costs) / optimal_costs * 100.0

            factors.append(factor_pct)
            runtimes.append(runtime)
            rows.append([tspi, optimal_costs, total_costs, f"{factor_pct:.2f}%", f"{runtime:.3f}s"])

            logger.info(
                "  Result: Total cost = %-10s | Factor = %.2f%% | Runtime = %.3fs",
                total_costs,
                factor_pct,
                runtime,
            )
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received, stopping benchmark.")

    if not rows:
        logger.warning("No benchmark results to display.")
        return 1

    # Summary statistics across all completed instances
    min_factor = min(factors)
    max_factor = max(factors)
    arith_mean = statistics.mean(factors)
    geom_mean = statistics.geometric_mean(factors)
    median_factor = statistics.median(factors)
    total_runtime = sum(runtimes)

    headers = ["Instance", "Costs of optimal route", "Costs of RFA route", "Cost factor", "Runtime"]
    table = tabulate(rows, headers=headers)
    summary = (
        f"Summary ({len(rows)}/{len(instances)} instances):\n"
        f"  Min cost factor:               {min_factor:.2f}%\n"
        f"  Mean cost factor (arithmetic): {arith_mean:.2f}%\n"
        f"  Mean cost factor (geometric):  {geom_mean:.2f}%\n"
        f"  Median cost factor:            {median_factor:.2f}%\n"
        f"  Max cost factor:               {max_factor:.2f}%\n"
        f"  Total runtime:                 {total_runtime:.3f}s"
    )

    logger.info("\n%s\n\n%s", table, summary)

    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = create_argument_parser()
    args = parser.parse_args(argv)

    logging.basicConfig(
        format="%(levelname)s | %(message)s",
        level=logging.DEBUG if args.verbose else logging.INFO,
    )

    try:
        instances = resolve_tsplib_instances(args.tsplib, args.tsplib_dir)
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 1

    return run_benchmark(
        instances=instances,
        tsplib_dir=args.tsplib_dir,
        folding_strategy_name=args.folding_strategy,
        unfolding_strategy_name=args.unfolding_strategy,
        post_uncross=args.post_uncross,
        seed=args.seed,
    )


if __name__ == "__main__":
    sys.exit(main())
