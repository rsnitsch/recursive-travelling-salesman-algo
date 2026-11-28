#!/usr/bin/env python3
"""In-process tests for the rfa-tsp benchmark CLI."""

import pytest

from rfa_tsp.cli_benchmark import main as cli_benchmark_main


def test_benchmark_help(capsys: pytest.CaptureFixture[str]) -> None:
    """Verify the benchmark CLI prints help and exits with code 0."""
    with pytest.raises(SystemExit) as exc_info:
        cli_benchmark_main(["--help"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "usage:" in captured.out.lower()


@pytest.mark.parametrize("trials", ["1", "2"])
def test_benchmark_with_trials(trials: str) -> None:
    """Verify the benchmark CLI runs on a small TSPLIB instance."""
    assert cli_benchmark_main(["--tsplib", "pr76", "--trials", trials]) == 0
