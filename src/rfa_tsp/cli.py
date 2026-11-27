#!/usr/bin/env python3
"""
CLI for executing, visualizing, and exporting the recursive-fold-algorithm (RFA)
on a single metric travelling salesman problem (TSP) instance.

Copyright (c) 2010-2026 Robert Nitsch
"""

import argparse
import datetime
import json
import logging
import math
import random
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from tqdm import tqdm

from . import __version__
from .cli_common import (
    DEFAULT_FOLDING_STRATEGY,
    DEFAULT_UNFOLDING_STRATEGY,
    FOLDING_STRATEGIES,
    UNFOLDING_STRATEGIES,
    positive_int,
    setup_logging,
)
from .common import Route, generate_random_nodes, load_nodes_from_tsplib_file, optimal_solutions
from .rfa import (
    FoldingStrategy,
    UnfoldingStrategy,
)
from .ui import Renderer

logger = logging.getLogger(__name__)


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
        default=DEFAULT_FOLDING_STRATEGY,
        choices=list(FOLDING_STRATEGIES),
        help=f"default: {DEFAULT_FOLDING_STRATEGY}",
    )
    parser.add_argument(
        "--unfolding-strategy",
        type=str,
        default=DEFAULT_UNFOLDING_STRATEGY,
        choices=list(UNFOLDING_STRATEGIES),
        help=f"default: {DEFAULT_UNFOLDING_STRATEGY}",
    )
    parser.add_argument(
        "-s",
        "--seed",
        type=int,
        default=0,
        help="Random number generator seed for the RFA algorithm (default = 0).",
    )
    parser.add_argument(
        "-t",
        "--trials",
        type=positive_int,
        default=1,
        help="Number of consecutive seeds to try (starting from --seed), keeping the best route (default = 1).",
    )
    parser.add_argument(
        "--save-trials",
        nargs="?",
        const="auto",
        default=None,
        metavar="PATH",
        help="Save per-trial results to JSON (default filename: trial-YYYY-MM-DD-HH-mm-ss.json).",
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
        "--renderer",
        type=str,
        default="disabled",
        choices=["disabled", "matplotlib"],
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
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    return parser


def get_renderer_by_name(name: str) -> Renderer | None:
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


class OnlineStats:
    """Numerically stable online mean and sample standard deviation (Welford's algorithm)."""

    def __init__(self) -> None:
        self.count = 0
        self.mean = 0.0
        self._m2 = 0.0

    def update(self, value: float) -> None:
        self.count += 1
        delta = value - self.mean
        self.mean += delta / self.count
        delta2 = value - self.mean
        self._m2 += delta * delta2

    @property
    def stdev(self) -> float:
        if self.count < 2:
            return 0.0
        return math.sqrt(self._m2 / (self.count - 1))


def write_trials_json(path: Path, meta: dict[str, object], trials: list[dict[str, object]]) -> None:
    """Atomically write trial metadata and results to a JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    payload = {"meta": meta, "trials": trials}
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def run_single_trial(
    *,
    nodes,
    ceil_2d: bool,
    folding_strategy: FoldingStrategy,
    unfolding_strategy: UnfoldingStrategy,
    post_uncross: bool,
    seed: int,
    renderer: Renderer | None,
) -> tuple[Route, int, float]:
    """Run one RFA trial for a given seed and return (route, total_costs, runtime)."""
    random.seed(seed)
    start_time = time.perf_counter()

    folded = folding_strategy.fold(nodes, ceil_2d, renderer)
    assert len(folded) <= 3, "Folding did not reduce number of nodes to 3."

    route = Route(unfolding_strategy.unfold(folded, ceil_2d, renderer))
    if post_uncross:
        route = route.intersection_cleanup()
        if renderer:
            renderer.record_post_process(route, cost=route.get_total_costs(ceil_2d))

    runtime = time.perf_counter() - start_time
    total_costs = route.get_total_costs(ceil_2d)
    return route, total_costs, runtime


def main(argv: Sequence[str] | None = None) -> int:
    parser = create_argument_parser()
    args = parser.parse_args(argv)

    setup_logging(args.verbose)

    try:
        nodes, ceil_2d, tspi = load_instance(args.instance, args.number_of_nodes, args.tsplib_dir)
    except (ValueError, FileNotFoundError) as exc:
        logger.error("%s", exc)
        return 1

    logger.info("Instance:           %s (%d nodes)", args.instance, len(nodes))
    logger.info("Folding strategy:   %s", args.folding_strategy)
    logger.info("Unfolding strategy: %s", args.unfolding_strategy)
    logger.info("Post-uncross:       %s", args.post_uncross)
    logger.info("Weighted centroids: %s", args.weighted_centroids)

    folding_strategy = FOLDING_STRATEGIES[args.folding_strategy](weighted_centroids=args.weighted_centroids)
    unfolding_strategy = UNFOLDING_STRATEGIES[args.unfolding_strategy]()

    # Automatically use matplotlib when export is requested without an interactive renderer
    show_window = args.renderer != "disabled"
    if args.export is not None and args.renderer == "disabled":
        renderer_instance = get_renderer_by_name("matplotlib")
    else:
        renderer_instance = get_renderer_by_name(args.renderer)

    optimal_costs = optimal_solutions.get(tspi) if tspi is not None else None

    if args.trials == 1:
        logger.info("Seed:               %d", args.seed)
        _, total_costs, runtime = run_single_trial(
            nodes=nodes,
            ceil_2d=ceil_2d,
            folding_strategy=folding_strategy,
            unfolding_strategy=unfolding_strategy,
            post_uncross=args.post_uncross,
            seed=args.seed,
            renderer=renderer_instance,
        )
        logger.info("Total length:       %s", total_costs)
        if optimal_costs is not None:
            overhead_pct = (float(total_costs) / optimal_costs - 1.0) * 100.0
            logger.info("Optimal route:      %s (overhead of RFA route: +%.2f%%)", optimal_costs, overhead_pct)
        logger.info("Runtime:            %.3fs", runtime)
        logger.info("Runtime per node:   %.3fµs", runtime / len(nodes) * 1e6)
    else:
        if args.folding_strategy == "outside-in":
            parser.error(
                "Folding strategy 'outside-in' is deterministic; multiple trials would yield identical results."
            )

        logger.info("Trials:             %d (seeds %d..%d)", args.trials, args.seed, args.seed + args.trials - 1)

        run_started_at = datetime.datetime.now()
        save_path: Path | None = None
        if args.save_trials is not None:
            if args.save_trials == "auto":
                save_path = Path(f"trial-{run_started_at.strftime('%Y-%m-%d-%H-%M-%S')}.json")
            else:
                save_path = Path(args.save_trials)
            logger.info("Saving trials to:   %s", save_path)

        meta: dict[str, object] = {
            "version": __version__,
            "timestamp": run_started_at.isoformat(timespec="seconds"),
            "argv": sys.argv[1:],
            "instance": args.instance,
            "nodes": len(nodes),
            "optimal_length": optimal_costs,
            "folding_strategy": args.folding_strategy,
            "unfolding_strategy": args.unfolding_strategy,
            "post_uncross": args.post_uncross,
            "seed_start": args.seed,
            "trials_requested": args.trials,
            "weighted_centroids": args.weighted_centroids,
        }

        best_cost: int | None = None
        best_seed = args.seed
        best_runtime = 0.0
        total_runtime = 0.0
        completed = 0
        stats = OnlineStats()
        trial_records: list[dict[str, object]] = []
        last_save = time.perf_counter()

        try:
            with tqdm(range(args.trials), desc="Trials", unit="trial") as pbar:
                for i in pbar:
                    current_seed = args.seed + i
                    _, cost, runtime = run_single_trial(
                        nodes=nodes,
                        ceil_2d=ceil_2d,
                        folding_strategy=folding_strategy,
                        unfolding_strategy=unfolding_strategy,
                        post_uncross=args.post_uncross,
                        seed=current_seed,
                        renderer=None,
                    )
                    completed += 1
                    total_runtime += runtime
                    stats.update(float(cost))

                    if save_path is not None:
                        trial_records.append({"seed": current_seed, "length": cost, "runtime": round(runtime, 6)})

                    if best_cost is None or cost < best_cost:
                        best_cost = cost
                        best_seed = current_seed
                        best_runtime = total_runtime

                    if optimal_costs is not None:
                        best_oh = (float(best_cost) / optimal_costs - 1.0) * 100.0
                        mean_oh = (stats.mean / optimal_costs - 1.0) * 100.0
                        std_oh = (stats.stdev / optimal_costs) * 100.0
                        best_str = f"{best_cost} (+{best_oh:.2f}%)"
                        mean_str = f"+{mean_oh:.2f}% ± {std_oh:.2f}%"
                    else:
                        best_str = f"{best_cost}"
                        mean_str = f"{stats.mean:.0f} ± {stats.stdev:.0f}"

                    pbar.set_postfix(
                        best=best_str,
                        mean=mean_str,
                        seed=best_seed,
                        refresh=False,
                    )

                    # Periodically flush trial results (every 5s) during long runs
                    if save_path is not None and (time.perf_counter() - last_save) >= 5.0:
                        write_trials_json(save_path, meta, trial_records)
                        last_save = time.perf_counter()
        except KeyboardInterrupt:
            logger.info("Interrupted after %d/%d trials.", completed, args.trials)

        if best_cost is None:
            logger.warning("No trials completed.")
            return 1

        if save_path is not None:
            write_trials_json(save_path, meta, trial_records)
            logger.info("Saved %d trial(s) to %s", len(trial_records), save_path)

        avg_time = total_runtime / completed
        cv_pct = (stats.stdev / stats.mean * 100.0) if stats.mean > 0 else 0.0

        logger.info("Best seed:          %d (found at %.3fs)", best_seed, best_runtime)
        logger.info("Best length:        %s", best_cost)
        logger.info("Mean length:        %.1f ± %.1f (CV: %.2f%%)", stats.mean, stats.stdev, cv_pct)
        if optimal_costs is not None:
            best_oh = (float(best_cost) / optimal_costs - 1.0) * 100.0
            mean_oh = (stats.mean / optimal_costs - 1.0) * 100.0
            std_oh = (stats.stdev / optimal_costs) * 100.0
            logger.info("Optimal route:      %s", optimal_costs)
            logger.info("Best overhead:      +%.2f%%", best_oh)
            logger.info("Mean overhead:      +%.2f%% ± %.2f%% (σ)", mean_oh, std_oh)
        logger.info("Runtime:            %.3fs total (%.5fs/trial avg)", total_runtime, avg_time)
        logger.info("Runtime per node:   %.3fµs", avg_time / len(nodes) * 1e6)

        # Replay only the winning seed if visualization or export was requested
        if renderer_instance is not None:
            logger.info("Replaying best seed (%d) for rendering/export...", best_seed)
            run_single_trial(
                nodes=nodes,
                ceil_2d=ceil_2d,
                folding_strategy=folding_strategy,
                unfolding_strategy=unfolding_strategy,
                post_uncross=args.post_uncross,
                seed=best_seed,
                renderer=renderer_instance,
            )

    if args.export is not None:
        if hasattr(renderer_instance, "export"):
            assert renderer_instance is not None
            renderer_instance.export(args.export, fps=args.export_fps)  # pyright: ignore[reportAttributeAccessIssue]
        else:
            logger.error("Selected renderer '%s' does not support animation export.", args.renderer)

    if show_window and renderer_instance:
        renderer_instance.wait_until_closed()

    return 0


if __name__ == "__main__":
    sys.exit(main())
