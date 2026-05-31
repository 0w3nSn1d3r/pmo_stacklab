"""Stretch algorithms: compress dynamic range so faint structure becomes visible.

The headline Post-Process subprocess, and the one that best rewards
experimentation. Astronomical data is dominated by a few bright stars while the
interesting nebulosity is orders of magnitude fainter; a non-linear stretch
remaps the (already normalized [0,1]) intensities so the faint end is boosted
relative to the bright end. The choice of stretch and its tuning is exactly the
kind of decision the app exists to let students explore.

Coordinates astropy.visualization stretch classes (which map [0,1] -> [0,1])
rather than implementing the transfer functions:

* ``linear`` -- no compression (baseline; shows why a stretch is needed).
* ``sqrt`` -- mild compression.
* ``log`` -- strong compression, tunable.
* ``asinh`` -- inverse hyperbolic sine; the popular choice that brightens faint
  signal while keeping bright stars from saturating, tunable via ``a``.

Stretches assume input already normalized to [0, 1] (the intensity-scaling step),
so these operators clip to that range before applying the transfer function.
"""
from __future__ import annotations

import numpy as np
from astropy.visualization import (
    AsinhStretch,
    LinearStretch,
    LogStretch,
    SqrtStretch,
)

from ..core import Operator
from ._common import per_filter_operator


def _apply(stretch) -> Operator:
    """Build an operator applying an astropy ``stretch`` to each frame.

    Input is clipped to [0, 1] first, since the stretch transfer functions are
    only defined there; if intensity-scaling has run, the clip is a no-op.
    """

    def transform(data: np.ndarray) -> np.ndarray:
        clipped = np.clip(np.asarray(data, dtype=float), 0.0, 1.0)
        return np.asarray(stretch(clipped), dtype=float)

    return per_filter_operator(transform)


def build_linear() -> Operator:
    """No non-linear compression (baseline)."""
    return _apply(LinearStretch())


def build_sqrt() -> Operator:
    """Square-root stretch: mild faint-end boost."""
    return _apply(SqrtStretch())


def build_log(a: float = 1000.0) -> Operator:
    """Logarithmic stretch.

    :param a: contrast parameter; larger ``a`` compresses the bright end harder,
        boosting faint signal more aggressively.
    """
    return _apply(LogStretch(a=a))


def build_asinh(a: float = 0.1) -> Operator:
    """Inverse-hyperbolic-sine stretch.

    :param a: the value (in [0, 1]) mapped to the linear/log transition; smaller
        ``a`` boosts faint signal more. The common, well-behaved default choice.
    """
    return _apply(AsinhStretch(a=a))
