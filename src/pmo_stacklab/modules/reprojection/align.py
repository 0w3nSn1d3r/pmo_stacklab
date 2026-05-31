"""Alignment algorithms: resample each frame onto the reference grid.

Alignment is the second of Reproject's two subprocesses. Given the per-frame
inverse maps produced by registration, it resamples every light frame onto the
reference grid using skimage's ``warp``. The only thing that varies between the
algorithms is the interpolation order -- the knob that trades sharpness against
ringing/aliasing -- which is exactly the resampling-quality juxtaposition the
pedagogy is after:

* ``nearest`` (order 0) -- nearest-neighbour; blocky, no new values, fastest.
* ``bilinear`` (order 1) -- smooth, mild blurring; the common default.
* ``bicubic`` (order 3) -- sharper, but can overshoot near bright edges.

An align algorithm is a function ``(frame, inverse_map) -> resampled_frame`` that
warps one frame; the Reproject coordinator pairs it with the registration result.
Because resampling changes only pixel values (the grid becomes the reference's),
the frame's WCS/header/mask are preserved by copying the frame and replacing its
data, mirroring how calibration rewraps frames.
"""
from __future__ import annotations

from collections.abc import Callable

import numpy as np
from astropy.nddata import CCDData
from skimage.transform import warp

from .register import InverseMap

# An align algorithm warps one frame using a registration inverse map.
AlignOp = Callable[[CCDData, InverseMap], CCDData]

# Human-facing interpolation name -> skimage spline order.
_ORDERS = {"nearest": 0, "bilinear": 1, "bicubic": 3}


def build_warp(interpolation: str = "bilinear") -> AlignOp:
    """Build an alignment operator that resamples via skimage ``warp``.

    :param interpolation: one of ``"nearest"``, ``"bilinear"``, ``"bicubic"``.
    :returns: a callable ``(frame, inverse_map) -> resampled CCDData``.
    :raises ValueError: for an unknown interpolation name.
    """
    if interpolation not in _ORDERS:
        raise ValueError(
            f"unknown interpolation {interpolation!r}; "
            f"expected one of {sorted(_ORDERS)}"
        )
    order = _ORDERS[interpolation]

    def align(frame: CCDData, inverse_map: InverseMap) -> CCDData:
        resampled = warp(
            np.asarray(frame.data, dtype=float),
            inverse_map,
            order=order,
            mode="constant",
            cval=np.nan,  # off-grid pixels become NaN, flagged in the mask below
            preserve_range=True,
        )
        # Pixels that fell outside the source frame are invalid; record them in the
        # mask (unioned with any existing mask) and zero the NaNs so the array
        # stays finite for downstream arithmetic.
        invalid = np.isnan(resampled)
        if frame.mask is not None:
            invalid = invalid | np.asarray(frame.mask, dtype=bool)
        resampled = np.where(np.isnan(resampled), 0.0, resampled)

        out = frame.copy()
        out.data = resampled
        out.mask = invalid
        return out

    return align
