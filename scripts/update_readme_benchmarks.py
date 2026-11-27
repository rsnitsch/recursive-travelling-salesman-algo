#!/usr/bin/env python3
"""
Run TSPLIB95 benchmarks and update the marked Results tables in README.md.

Copyright (c) 2010-2026 Robert Nitsch
"""

import argparse
import logging
import re
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from pathlib import Path

logger = logging.getLogger(__name__)


def create_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run RFA benchmarks (default and pure unfolding) and update README.md in place."
    )
    parser.add_argument(
        "--readme",
        type=Path,
        default=Path("README.md"),
        help="Path to the README.md file to update (default: README.md).",
    )
    parser.add_argument(
        "--trials-default",
        type=int,
        default=10,
        help="Number of trials per instance for the default strategy benchmark (default: 10).",
    )
    parser.add_argument(
        "--trials-pure",
        type=int,
        default=100,
        help="Number of trials per instance for the pure RFA (breadth-first unfolding) benchmark (default: 100).",
    )
    parser.add_argument(
        "--cooldown",
        type=float,
        default=5.0,
        help="Cooldown in seconds between instances passed to rfa-tsp-benchmark (default: 5.0).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=0,
        help="Base RNG seed passed to rfa-tsp-benchmark (default: 0).",
    )
    parser.add_argument(
        "--skip-format",
        action="store_true",
        help="Skip formatting README.md with mdformat after updating.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose (DEBUG) logging output.",
    )
    return parser


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)-8s | %(message)s",
    )


def run_benchmark_to_markdown(
    output_path: Path,
    *,
    trials: int,
    cooldown: float,
    seed: int,
    unfolding_strategy: str | None = None,
    verbose: bool = False,
) -> str:
    """Invoke rfa-tsp-benchmark and return the generated Markdown content."""
    cmd = [
        "uv",
        "run",
        "rfa-tsp-benchmark",
        "--trials",
        str(trials),
        "--cooldown",
        str(cooldown),
        "--seed",
        str(seed),
        "--export-markdown",
        str(output_path),
    ]
    if unfolding_strategy is not None:
        cmd.extend(["--unfolding-strategy", unfolding_strategy])
    if verbose:
        cmd.append("--verbose")

    logger.info("Running command: %s", " ".join(cmd))
    subprocess.run(cmd, check=True)
    return output_path.read_text(encoding="utf-8").strip()


def replace_marked_section(content: str, marker_name: str, replacement: str) -> str:
    """Replace text between <!-- BEGIN:<marker_name> --> and <!-- END:<marker_name> -->."""
    begin_marker = f"<!-- BEGIN:{marker_name} -->"
    end_marker = f"<!-- END:{marker_name} -->"

    pattern = re.compile(
        rf"({re.escape(begin_marker)}\n).*?(\n{re.escape(end_marker)})",
        flags=re.DOTALL,
    )
    if not pattern.search(content):
        raise ValueError(f"Markers {begin_marker} ... {end_marker} not found in README.")

    return pattern.sub(rf"\1\n{replacement}\n\2", content, count=1)


def format_readme(readme_path: Path) -> None:
    """Format README.md using mdformat with GFM and dollarmath plugins."""
    cmd = [
        "uvx",
        "--with",
        "mdformat-gfm",
        "--with",
        "mdformat-dollarmath",
        "mdformat",
        "--wrap",
        "120",
        str(readme_path),
    ]
    logger.info("Formatting %s with mdformat...", readme_path)
    subprocess.run(cmd, check=True)


def main(argv: Sequence[str] | None = None) -> int:
    parser = create_argument_parser()
    args = parser.parse_args(argv)
    configure_logging(args.verbose)

    readme_path: Path = args.readme
    if not readme_path.is_file():
        logger.error("README file not found: %s", readme_path)
        return 1

    with tempfile.TemporaryDirectory() as tmp_dir_str:
        tmp_dir = Path(tmp_dir_str)
        default_md_path = tmp_dir / "results_default.md"
        pure_md_path = tmp_dir / "results_pure.md"

        logger.info("Running default configuration benchmark (%d trials)...", args.trials_default)
        default_md = run_benchmark_to_markdown(
            default_md_path,
            trials=args.trials_default,
            cooldown=args.cooldown,
            seed=args.seed,
            unfolding_strategy=None,
            verbose=args.verbose,
        )

        logger.info("Running pure RFA benchmark without local 2-opt (%d trials)...", args.trials_pure)
        pure_md = run_benchmark_to_markdown(
            pure_md_path,
            trials=args.trials_pure,
            cooldown=args.cooldown,
            seed=args.seed,
            unfolding_strategy="breadth-first",
            verbose=args.verbose,
        )

    logger.info("Updating %s...", readme_path)
    readme_text = readme_path.read_text(encoding="utf-8")
    try:
        readme_text = replace_marked_section(readme_text, "RESULTS_DEFAULT", default_md)
        readme_text = replace_marked_section(readme_text, "RESULTS_PURE", pure_md)
    except ValueError as exc:
        logger.error("%s", exc)
        return 1

    readme_path.write_text(readme_text, encoding="utf-8")
    logger.info("Updated benchmark sections in %s.", readme_path)

    if not args.skip_format:
        format_readme(readme_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
