#!/usr/bin/env python3
"""In-process tests for the main rfa-tsp CLI."""

import json
from pathlib import Path

import pytest

from rfa_tsp.cli import main as cli_main


def test_cli_help(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify the CLI prints help and exits with code 0."""
    with pytest.raises(SystemExit) as exc_info:
        cli_main(["--help"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "usage:" in captured.out.lower()


def test_single_run_tsplib() -> None:
    """Verify a standard single run on a small TSPLIB instance succeeds."""
    assert cli_main(["tsplib:pr76"]) == 0


@pytest.mark.parametrize(
    "strategy",
    ["breadth-first-mutual-nn", "breadth-first", "random-nn", "outside-in"],
)
def test_folding_strategies(strategy: str) -> None:
    """Verify a standard single run succeeds for all folding strategies."""
    assert cli_main(["tsplib:pr76", "--folding-strategy", strategy]) == 0


@pytest.mark.parametrize(
    "strategy",
    ["breadth-first", "breadth-first-2opt"],
)
def test_unfolding_strategies(strategy: str) -> None:
    """Verify a standard single run succeeds for all unfolding strategies."""
    assert cli_main(["tsplib:pr76", "--unfolding-strategy", strategy]) == 0


def test_weighted_centroids() -> None:
    """Verify a standard single run succeeds with --weighted-centroids."""
    assert cli_main(["tsplib:pr76", "--weighted-centroids"]) == 0


def test_post_uncross() -> None:
    """Verify a standard single run succeeds with --post-uncross."""
    assert cli_main(["tsplib:pr76", "--post-uncross"]) == 0


def test_multi_trial_and_save_json(tmp_path: Path) -> None:
    """Verify multi-trial execution and atomic JSON result export."""
    out_file = tmp_path / "trials.json"
    exit_code = cli_main(["tsplib:pr76", "--trials", "5", "--save-trials", str(out_file)])

    assert exit_code == 0
    assert out_file.is_file()

    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    assert len(data) > 0


@pytest.mark.parametrize("flag", ["-v", "--verbose"])
def test_verbose_flag(flag: str) -> None:
    """Verify verbose logging flags do not crash the CLI."""
    assert cli_main(["tsplib:pr76", flag]) == 0
