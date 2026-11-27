#!/usr/bin/env python3
"""Generate seed sensitivity plots for README.md."""

import argparse
import logging
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)

INSTANCES: list[tuple[str, int]] = [
    ("pr76", 5000),
    ("pla7397", 300),
    ("usa13509", 200),
]


def _run_command(cmd: list[str]) -> None:
    """Run a shell command and raise on non-zero exit code."""
    logger.debug("Executing command: %s", " ".join(cmd))
    subprocess.run(cmd, check=True)


def generate_plots(docs_dir: Path) -> None:
    """Run multi-trial benchmarks and export seed sensitivity plots."""
    docs_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="rfa-tsp-trials-") as tmp:
        tmp_dir = Path(tmp)
        for name, trials in INSTANCES:
            json_path = tmp_dir / f"trial-{name}.json"
            png_path = docs_dir / f"rfa-tsp-seed-sensitivity_tsplib-{name}.png"

            logger.info("Running tsplib:%s (%d trials)...", name, trials)
            _run_command(
                [
                    "uv",
                    "run",
                    "rfa-tsp",
                    f"tsplib:{name}",
                    "--trials",
                    str(trials),
                    "--save-trials",
                    str(json_path),
                ]
            )

            logger.info("Exporting plot to %s...", png_path)
            _run_command(
                [
                    "uv",
                    "run",
                    "rfa-tsp-plot-trials",
                    str(json_path),
                    "--export",
                    str(png_path),
                ]
            )


def main() -> None:
    """Parse CLI arguments and run plot generation."""
    parser = argparse.ArgumentParser(description="Regenerate seed sensitivity plots for README.md.")
    parser.add_argument(
        "--docs-dir",
        type=Path,
        default=Path("docs"),
        help="Output directory for exported PNG plots (default: docs).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable debug logging.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        format="%(levelname)-8s | %(message)s",
        level=logging.DEBUG if args.verbose else logging.INFO,
    )

    generate_plots(args.docs_dir)
    logger.info("Done. Plots updated in %s.", args.docs_dir)


if __name__ == "__main__":
    main()
