#!/usr/bin/env python3
"""In-process tests for the rfa-tsp plot-trials CLI."""

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import pytest

from rfa_tsp.cli import main as cli_main
from rfa_tsp.cli_plot_trials import main as cli_plot_trials_main

# Ensure headless rendering in CI environments without a display server
matplotlib.use("Agg")


def test_plot_trials_help(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify the plot-trials CLI prints help and exits with code 0."""
    with pytest.raises(SystemExit) as exc_info:
        cli_plot_trials_main(["--help"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "usage:" in captured.out.lower()


def test_plot_trials_end_to_end_export(tmp_path: Path) -> None:
    """Verify generating trials JSON and exporting a plot image succeeds end-to-end."""
    trials_file = tmp_path / "trials.json"
    plot_file = tmp_path / "plot.png"

    try:
        # Generate real trial output to catch schema mismatches between writer and plotter
        assert cli_main(["tsplib:pr76", "--trials", "5", "--save-trials", str(trials_file)]) == 0
        assert trials_file.is_file()

        assert cli_plot_trials_main([str(trials_file), "--export", str(plot_file)]) == 0
        assert plot_file.is_file()
        assert plot_file.stat().st_size > 0
    finally:
        plt.close("all")


def test_plot_trials_missing_file(tmp_path: Path) -> None:
    """Verify the plot-trials CLI returns exit code 1 on a missing input file."""
    missing_file = tmp_path / "does_not_exist.json"
    assert cli_plot_trials_main([str(missing_file)]) == 1
