#!/usr/bin/env python3
"""Basic smoke tests to verify rfa-tsp across Python versions."""

import json
import subprocess
import sys
from pathlib import Path

import pytest


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """Run rfa-tsp as a module using the current Python interpreter."""
    return subprocess.run(
        [sys.executable, "-m", "rfa_tsp", *args],
        capture_output=True,
        text=True,
        check=False,
    )


def test_cli_help() -> None:
    """Verify the CLI entry point starts and prints help."""
    result = _run_cli("--help")
    assert result.returncode == 0
    assert "usage:" in result.stdout.lower()


def test_single_run_tsplib() -> None:
    """Verify a standard single run on a small TSPLIB instance succeeds."""
    result = _run_cli("tsplib:pr76")
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "strategy",
    ["breadth-first-mutual-nn", "breadth-first", "random-nn", "outside-in"],
)
def test_folding_strategies(strategy: str) -> None:
    """Verify a standard single run succeeds for all folding strategies."""
    result = _run_cli("tsplib:pr76", "--folding-strategy", strategy)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "strategy",
    ["breadth-first", "breadth-first-2opt"],
)
def test_unfolding_strategies(strategy: str) -> None:
    """Verify a standard single run succeeds for all unfolding strategies."""
    result = _run_cli("tsplib:pr76", "--unfolding-strategy", strategy)
    assert result.returncode == 0, result.stderr


def test_weighted_centroids() -> None:
    """Verify a standard single run succeeds with --weighted-centroids."""
    result = _run_cli("tsplib:pr76", "--weighted-centroids")
    assert result.returncode == 0, result.stderr


def test_post_uncross() -> None:
    """Verify a standard single run succeeds with --post-uncross."""
    result = _run_cli("tsplib:pr76", "--post-uncross")
    assert result.returncode == 0, result.stderr


def test_multi_trial_and_save_json(tmp_path: Path) -> None:
    """Verify multi-trial execution and atomic JSON result export."""
    out_file = tmp_path / "trials.json"
    result = _run_cli(
        "tsplib:pr76",
        "--trials",
        "5",
        "--save-trials",
        str(out_file),
    )
    assert result.returncode == 0, result.stderr
    assert out_file.is_file()

    data = json.loads(out_file.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    assert len(data) > 0


@pytest.mark.parametrize("flag", ["-v", "--verbose"])
def test_verbose_flag(flag: str) -> None:
    """Verify verbose logging flags do not crash the CLI."""
    result = _run_cli("tsplib:pr76", flag)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize("trials", ["1", "2"])
def test_benchmark_with_trials(trials: str) -> None:
    """Verify the benchmark CLI runs on a small TSPLIB instance."""
    result = subprocess.run(
        [sys.executable, "-m", "rfa_tsp.cli_benchmark", "--tsplib", "pr76", "--trials", trials],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
