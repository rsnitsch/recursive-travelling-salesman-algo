#!/usr/bin/env python3
"""
Common functionality for rfa-tsp cli scripts.

Copyright (c) 2010-2026 Robert Nitsch
"""

import argparse
import logging
from datetime import datetime

from . import __version__
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
DEFAULT_FOLDING_STRATEGY = "breadth-first-mutual-nn"

UNFOLDING_STRATEGIES: dict[str, type[UnfoldingStrategy]] = {
    "breadth-first": UnfoldingStrategyBreadthFirst,
    "breadth-first-2opt": UnfoldingStrategyBreadthFirstWithLocal2Opt,
}
DEFAULT_UNFOLDING_STRATEGY = "breadth-first-2opt"


def positive_int(value: str) -> int:
    """Argparse type validator for strictly positive integers."""
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be >= 1")
    return parsed


def non_negative_float(value: str) -> float:
    """Argparse type validator for non-negative floats."""
    parsed = float(value)
    if parsed < 0.0:
        raise argparse.ArgumentTypeError("must be >= 0")
    return parsed


def setup_logging(verbose: bool) -> None:
    """Configure root logging and emit version and timestamp."""
    if verbose:
        log_format = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    else:
        log_format = "%(levelname)-8s | %(message)s"

    logging.basicConfig(
        format=log_format,
        datefmt="%H:%M:%S",
        level=logging.DEBUG if verbose else logging.INFO,
    )

    logger.info("rfa-tsp version:    %s", __version__)
    logger.info("Timestamp:          %s", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
