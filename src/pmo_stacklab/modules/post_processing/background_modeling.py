"""Background-modeling algorithms: estimate and subtract the sky background.

The first Post-Process subprocess. Light pollution, sky glow, and optical
vignetting leave a smooth, additive background (often a gradient) over the image;
removing it flattens the field so faint structure stands out under the later
stretch. These operators estimate that background and subtract it, working on the
linear stacked data (before any normalization or stretch).

PMO StackLab coordinates established background estimators rather than
implementing them:

* ``none`` -- subtract nothing (baseline).
* ``global`` -- subtract a single constant (the median sky level); removes an
  overall pedestal but not gradients.
* ``2d`` -- subtract a smoothly varying 2-D background model from ``sep`` (the
  Source Extractor background), which removes gradients and vignetting.
"""
from __future__ import annotations

import numpy as np

from ..core import Operator
from ._common import per_filter_operator


def build_none() -> Operator:
    """No background subtraction (baseline)."""
    return per_filter_operator(lambda data: data)


def build_global() -> Operator:
    """Subtract a single constant background: the median pixel value."""

    def transform(data: np.ndarray) -> np.ndarray:
        return data - float(np.nanmedian(data))

    return per_filter_operator(transform)


def build_sep_2d(box_size: int = 64) -> Operator:
    """Subtract a smooth 2-D background model estimated by ``sep``.

    :param box_size: side length (pixels) of the mesh ``sep`` uses to estimate the
        spatially varying background; smaller follows finer structure but risks
        over-subtracting real signal.
    """
    import sep  # imported lazily; only this algorithm needs it

    def transform(data: np.ndarray) -> np.ndarray:
        # sep requires C-contiguous, native-byte-order float32/float64.
        arr = np.ascontiguousarray(data, dtype=np.float64)
        background = sep.Background(arr, bw=box_size, bh=box_size)
        return arr - background.back()

    return per_filter_operator(transform)
