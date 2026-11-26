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

from . import __version__
from .common import Route, load_nodes_from_tsplib_file, tsplib_get_optimal_solution
from .rfa import (
    FoldingStrategy,
    FoldingStrategyBreadthFirst,
    FoldingStrategyBreadthFirstMutualNearestNeighbor,
    FoldingStrategyOutsideIn,
    FoldingStrategyRandomWithNearestNeighbor,
    UnfoldingStrategy,
    UnfoldingStrategyBreadthFirst,
    UnfoldingStrategyBreadthFirstWithLocal2Opt,
)

logger = logging.getLogger(__name__)

FOLDING_STRATEGIES: dict[str, type[FoldingStrategy]] = {
    "breadth-first": FoldingStrategyBreadthFirst,
    "breadth-first-mutual-nn": FoldingStrategyBreadthFirstMutualNearestNeighbor,
    "random-nn": FoldingStrategyRandomWithNearestNeighbor,
    "outside-in": FoldingStrategyOutsideIn,
}

UNFOLDING_STRATEGIES: dict[str, type[UnfoldingStrategy]] = {
    "breadth-first": UnfoldingStrategyBreadthFirst,
    "breadth-first-2opt": UnfoldingStrategyBreadthFirstWithLocal2Opt,
}


def positive_int(value: str) -> int:
    """Argparse type validator for strictly positive integers."""
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return parsed


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
        help="Base random number generator seed; trial i uses seed + i (default = 0).",
    )
    parser.add_argument(
        "-t",
        "--trials",
        type=positive_int,
        default=1,
        help="Number of trials per instance with incrementing seeds (default = 1).",
    )
    parser.add_argument(
        "--post-uncross",
        action="store_true",
        default=False,
        help="Remove intersecting edges from the final route via 2-opt moves (default: off).",
    )
    parser.add_argument(
        "--weighted-centroids",
        action="store_true",
        default=False,
        help="Compute folded node positions as mass-weighted centroids instead of unweighted midpoints (default: off).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging output.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
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
    *,
    instances: list[str],
    tsplib_dir: Path,
    folding_strategy_name: str,
    unfolding_strategy_name: str,
    post_uncross: bool,
    seed: int,
    trials: int,
    weighted_centroids: bool,
) -> int:
    if not instances:
        logger.error("No TSPLIB instances selected.")
        return 1

    logger.info("Folding strategy:    %s", folding_strategy_name)
    logger.info("Unfolding strategy:  %s", unfolding_strategy_name)
    logger.info("Post-uncross:        %s", post_uncross)
    logger.info("Weighted centroids:  %s", weighted_centroids)
    logger.info("Seed:                %d", seed)
    logger.info("Trials per instance: %d", trials)
    logger.info("Running benchmark for %d TSPLIB instance(s): %s", len(instances), ", ".join(instances))

    rows: list[list[object]] = []
    mean_overheads: list[float] = []
    best_overheads: list[float] = []
    total_runtime = 0.0

    try:
        for tspi in instances:
            tsp_path = tsplib_dir / f"{tspi}.tsp"
            if not tsp_path.is_file():
                logger.error("TSPLIB file not found: %s", tsp_path)
                return 1

            logger.info("Processing TSPLIB instance %s...", tspi)
            nodes, ceil_2d = load_nodes_from_tsplib_file(tsp_path)
            optimal_costs = tsplib_get_optimal_solution(tspi)

            trial_costs: list[int] = []
            trial_overheads: list[float] = []
            trial_runtimes: list[float] = []

            for trial_idx in range(trials):
                trial_seed = seed + trial_idx
                random.seed(trial_seed)

                folding_strategy = FOLDING_STRATEGIES[folding_strategy_name](weighted_centroids=weighted_centroids)
                unfolding_strategy = UNFOLDING_STRATEGIES[unfolding_strategy_name]()

                logger.debug(
                    "Trial %d/%d (seed=%d): folding %d nodes...", trial_idx + 1, trials, trial_seed, len(nodes)
                )
                start_time = time.perf_counter()
                folded = folding_strategy.fold(nodes, ceil_2d, renderer=None)
                assert len(folded) <= 3, "Folding did not reduce number of nodes to 3."

                logger.debug("Trial %d/%d: unfolding...", trial_idx + 1, trials)
                route = Route(unfolding_strategy.unfold(folded, ceil_2d, renderer=None))
                if post_uncross:
                    logger.debug("Trial %d/%d: running post-uncross...", trial_idx + 1, trials)
                    route = route.intersection_cleanup()
                runtime = time.perf_counter() - start_time
                gc.collect()

                costs = route.get_total_costs(ceil_2d)
                overhead_pct = (float(costs) / optimal_costs - 1.0) * 100.0

                trial_costs.append(costs)
                trial_overheads.append(overhead_pct)
                trial_runtimes.append(runtime)

            total_runtime += sum(trial_runtimes)

            if trials == 1:
                total_costs = trial_costs[0]
                overhead_pct = trial_overheads[0]
                runtime = trial_runtimes[0]

                mean_overheads.append(overhead_pct)
                best_overheads.append(overhead_pct)
                rows.append([tspi, optimal_costs, total_costs, f"+{overhead_pct:.2f}%", f"{runtime:.3f}s"])

                logger.info(
                    "  Result: Total length = %-10s | Overhead vs. optimum = +%5.2f%% | Runtime = %.3fs",
                    total_costs,
                    overhead_pct,
                    runtime,
                )
            else:
                # best_costs = min(trial_costs)
                mean_costs = statistics.mean(trial_costs)
                best_oh = min(trial_overheads)
                mean_oh = statistics.mean(trial_overheads)
                std_oh = statistics.stdev(trial_overheads)
                mean_rt = statistics.mean(trial_runtimes)

                mean_overheads.append(mean_oh)
                best_overheads.append(best_oh)
                rows.append(
                    [
                        tspi,
                        optimal_costs,
                        # best_costs,
                        mean_costs,
                        # f"+{best_oh:.2f}%",
                        f"+{mean_oh:.2f}%",
                        f"±{std_oh:.2f}%",
                        f"{mean_rt:.3f}s",
                    ]
                )

                logger.info(
                    "  Result (%d trials): Best = +%5.2f%% | Mean = +%5.2f%% (±%.2f%%) | Mean runtime = %.3fs",
                    trials,
                    best_oh,
                    mean_oh,
                    std_oh,
                    mean_rt,
                )
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received, stopping benchmark.")

    if not rows:
        logger.warning("No benchmark results to display.")
        return 1

    min_overhead = min(mean_overheads)
    max_overhead = max(mean_overheads)
    arith_mean = statistics.mean(mean_overheads)
    median_overhead = statistics.median(mean_overheads)

    if trials == 1:
        headers = ["Instance", "Optimal route", "RFA route", "RFA vs. optimum", "Runtime"]
        summary = (
            f"Summary ({len(rows)}/{len(instances)} instances):\n"
            f"  Min overhead:               +{min_overhead:.2f}%\n"
            f"  Mean overhead (arithmetic): +{arith_mean:.2f}%\n"
            f"  Median overhead:            +{median_overhead:.2f}%\n"
            f"  Max overhead:               +{max_overhead:.2f}%\n"
            f"  Total runtime:              {total_runtime:.3f}s"
        )
    else:
        best_arith_mean = statistics.mean(best_overheads)
        headers = [
            "Instance",
            "Optimal",
            # "Best RFA",
            "Mean RFA",
            # "Best vs. opt.",
            "Mean vs. opt.",
            "Std",
            "Mean runtime",
        ]
        avg_runtime_per_trial = total_runtime / trials
        summary = (
            f"Summary ({len(rows)}/{len(instances)} instances, {trials} trials each):\n"
            f"  Mean of best overheads:     +{best_arith_mean:.2f}%\n"
            f"  Min mean overhead:          +{min_overhead:.2f}%\n"
            f"  Mean overhead (arithmetic): +{arith_mean:.2f}%\n"
            f"  Median mean overhead:       +{median_overhead:.2f}%\n"
            f"  Max mean overhead:          +{max_overhead:.2f}%\n"
            f"  Total runtime:              {total_runtime:.3f}s ({avg_runtime_per_trial:.5f}s / trial)"
        )

    table = tabulate(rows, headers=headers, floatfmt=".1f")
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
        trials=args.trials,
        weighted_centroids=args.weighted_centroids,
    )


if __name__ == "__main__":
    sys.exit(main())
