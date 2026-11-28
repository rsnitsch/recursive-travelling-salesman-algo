#!/usr/bin/env python3
"""Minimal subprocess smoke tests to verify module entry points."""

import os
import subprocess
import sys

import pytest


@pytest.mark.parametrize(
    "module",
    [
        "rfa_tsp",
        "rfa_tsp.cli_benchmark",
        "rfa_tsp.cli_plot_trials",
    ],
)
def test_module_entrypoint_help(module: str) -> None:
    """Verify each CLI module can be invoked via 'python -m'."""
    env = {**os.environ, "MPLBACKEND": "Agg"}
    result = subprocess.run(
        [sys.executable, "-m", module, "--help"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "usage:" in result.stdout.lower()
