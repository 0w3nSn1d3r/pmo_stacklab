"""Intensity-scaling algorithms: choose black/white points and normalize to [0,1].

The second Post-Process subprocess. After background subtraction the data is still
in arbitrary linear units with most pixels near the bottom of a huge range. Scaling
picks the low/high cut levels (the "black point" and "white point"), clips to them,
and normalizes to [0, 1] -- which is both a meaningful pedagogical choice (how
aggressively to clip highlights/shadows) and the normalized input the stretch step
requires.

Coordinates astropy.visualization interval classes rather than implementing the
cut-level statistics:

* ``minmax`` -- use the data's own min and max (no clipping; preserves everything).
* ``percentile`` -- clip a symmetric tail fraction (e.g. keep the central 99%);
  robust to a few hot pixels.
* ``zscale`` -- the IRAF ZScale algorithm, which picks limits well for
  high-dynamic-range astronomical images.
"""
from __future__ import annotations

import numpy as np
from astropy.visualization import (
    MinMaxInterval,
    PercentileInterval,
    ZScaleInterval,
)

from ..core import Operator
from ._common import per_filter_operator


def _apply(interval) -> Operator:
    """Build an operator that normalizes+clips each frame to [0,1] via ``interval``.

    The astropy interval's ``__call__`` maps data into [0, 1] and clips to the
    interval's limits, which is exactly the scaling operation.
    """

    def transform(data: np.ndarray) -> np.ndarray:
        return np.asarray(interval(data), dtype=float)

    return per_filter_operator(transform)


def build_minmax() -> Operator:
    """Normalize using the data's own minimum and maximum (no clipping)."""
    return _apply(MinMaxInterval())


def build_percentile(percentile: float = 99.0) -> Operator:
    """Clip a symmetric tail and normalize.

    :param percentile: central percentage of the data to keep (e.g. 99 clips the
        top and bottom 0.5%). Must be in (0, 100].
    """
    return _apply(PercentileInterval(percentile))


def build_zscale(contrast: float = 0.25) -> Operator:
    """Normalize using the IRAF ZScale algorithm.

    :param contrast: ZScale contrast parameter; smaller values map a narrower
        range of values across [0, 1], increasing apparent contrast.
    """
    return _apply(ZScaleInterval(contrast=contrast))
