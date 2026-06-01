"""Quality metrics computed on the full-resolution, linear frame data.

The numeric half of the pedagogy. Where the preview *shows* a step (downsampled
and display-stretched), metrics *quantify* it -- and they must be computed on the
full-resolution, LINEAR data, never on the downsampled/stretched preview copy, or
the numbers would describe the display transform rather than the image. A
teaching tool that reported misleading numbers would teach false intuitions, so
this module always reads the stored frame's own data.

Scope is deliberately minimal for now: basic descriptive statistics
(min/max/mean/median/std) plus the count of valid pixels. Noise/SNR and
source-detection metrics are a later unit.

Masked or non-finite pixels are excluded from every statistic. This matters
because reprojection leaves off-grid borders that are masked and zero-filled;
counting those zeros would bias the mean and std downward.
"""
from __future__ import annotations

import numpy as np
from astropy.nddata import CCDData


def _valid_pixels(frame: CCDData) -> np.ndarray:
    """Return the frame's finite, unmasked pixels as a flat float array.

    Combines the frame's mask (if any) with a non-finite check, so masked and
    NaN/inf pixels are dropped before any statistic is computed.
    """
    data = np.asarray(frame.data, dtype=float)
    valid = np.isfinite(data)
    if frame.mask is not None:
        valid &= ~np.asarray(frame.mask, dtype=bool)
    return data[valid]


def frame_metrics(frame: CCDData) -> dict[str, float | int]:
    """Compute basic descriptive statistics for one frame's valid pixels.

    :param frame: the stored (full-resolution, linear) frame to measure.
    :returns: a JSON-safe dict with ``count`` (valid-pixel count) and, when any
        valid pixels exist, ``min``/``max``/``mean``/``median``/``std`` as plain
        floats. If no pixels are valid, only ``count`` (0) is returned.
    """
    pixels = _valid_pixels(frame)
    if pixels.size == 0:
        return {"count": 0}
    return {
        "count": int(pixels.size),
        "min": float(pixels.min()),
        "max": float(pixels.max()),
        "mean": float(pixels.mean()),
        "median": float(np.median(pixels)),
        "std": float(pixels.std()),
    }
