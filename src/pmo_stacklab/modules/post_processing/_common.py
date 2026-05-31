"""Shared helpers for the per-filter, grayscale Post-Process operators.

Every Post-Process subprocess in this package transforms the single stacked frame
of each filter. These helpers factor out the two things they all do: rewrap a
frame with new pixel data while preserving its WCS/header/mask (Post-Process
changes only pixel values, never astrometry), and apply such a transform across
every filter of an :class:`~pmo_stacklab.modules.core.image_data.ImageData`.
"""
from __future__ import annotations

from collections.abc import Callable

import numpy as np
from astropy.nddata import CCDData

from ..core import ImageData, Operator


def with_data(frame: CCDData, new_data: np.ndarray) -> CCDData:
    """Copy ``frame`` but replace its pixel data, preserving WCS/header/mask/unit.

    Mirrors the calibration/align rewrap: post-processing alters only pixel values,
    so copying and swapping the data carries every other attribute through
    unchanged. (CCDData arithmetic methods are avoided because they drop the WCS.)
    """
    out = frame.copy()
    out.data = np.asarray(new_data, dtype=float)
    return out


def per_filter_operator(transform: Callable[[np.ndarray], np.ndarray]) -> Operator:
    """Wrap a pixel-array ``transform`` into an ``ImageData -> ImageData`` operator.

    The transform is applied to every frame of every filter (Post-Process normally
    runs after Stack, so there is one frame per filter, but applying to all frames
    keeps the operator valid earlier in a reordered pipeline too).

    :param transform: maps a 2-D pixel array to a transformed 2-D array.
    :returns: an :class:`~pmo_stacklab.modules.core.Operator`.
    """

    def operator(data: ImageData) -> ImageData:
        new_lights = {
            filt: tuple(
                with_data(frame, transform(np.asarray(frame.data, dtype=float)))
                for frame in frames
            )
            for filt, frames in data.lights.items()
        }
        return data.with_lights(new_lights)

    return operator
