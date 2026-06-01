"""Colour combination: map per-filter frames onto R/G/B and combine to one image.

This is a terminal, parallel operation rather than a pipeline ``Process``: its
input is the per-filter dict of stacked frames (not a single ImageData transform)
and its output is an :class:`RGBImage`, so it lives outside the generalized
``/api/run`` flow. It still reuses the algorithm registry for the *combine*
algorithm, so the methods are juxtaposable like everywhere else.

PMO StackLab only coordinates established methods here:

* ``lupton`` -- astropy's Lupton et al. asinh RGB, the standard astronomical
  colour-combine: an asinh stretch applied across the channels together so bright
  star cores keep their colour instead of saturating to white.
* ``linear`` -- independent per-channel percentile normalization; the simple,
  literal mapping, useful to contrast with Lupton's joint treatment.

The channel->filter assignment is the user's choice (any filter to any channel,
e.g. narrowband palettes); a channel with no assigned filter renders black.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping

import numpy as np
from astropy.nddata import CCDData
from astropy.visualization import PercentileInterval, make_lupton_rgb

from .image_data import ImageData
from .rgb_image import CHANNELS, RGBImage

# A combine algorithm turns three channel planes (each a 2-D float array or None
# for an unmapped channel) into an (H, W, 3) uint8 RGB array.
Combiner = Callable[[np.ndarray | None, np.ndarray | None, np.ndarray | None], np.ndarray]


def _channel_shape(
    r: np.ndarray | None, g: np.ndarray | None, b: np.ndarray | None
) -> tuple[int, int]:
    """Return the common (H, W) of the mapped channels, or raise if they disagree."""
    shapes = {c.shape for c in (r, g, b) if c is not None}
    if not shapes:
        raise ValueError("at least one channel must be mapped to a filter")
    if len(shapes) > 1:
        raise ValueError(f"mapped channels have mismatched shapes: {sorted(shapes)}")
    return next(iter(shapes))


def _zeros_for(
    channel: np.ndarray | None, shape: tuple[int, int]
) -> np.ndarray:
    """Return ``channel`` as a float array, or a zero plane when unmapped (black)."""
    if channel is None:
        return np.zeros(shape, dtype=float)
    return np.asarray(channel, dtype=float)


def build_lupton(stretch: float = 5.0, Q: float = 8.0) -> Combiner:
    """Lupton asinh RGB combine (astropy ``make_lupton_rgb``).

    :param stretch: the linear span (in data units, after per-channel scaling)
        mapped through the asinh; larger shows fainter signal.
    :param Q: the asinh softening; larger keeps bright cores from washing out.
    """

    def combine(r, g, b):
        shape = _channel_shape(r, g, b)
        # Scale each channel to a common ~[0,1] range first so `stretch`/`Q` act
        # comparably regardless of the filters' raw levels.
        planes = [_normalize(_zeros_for(c, shape)) for c in (r, g, b)]
        return make_lupton_rgb(*planes, stretch=stretch, Q=Q)

    return combine


def build_linear(percentile: float = 99.5) -> Combiner:
    """Independent per-channel percentile normalization to 8-bit (no joint asinh).

    :param percentile: central percentage kept when setting each channel's white
        point (clips the brightest tail).
    """

    def combine(r, g, b):
        shape = _channel_shape(r, g, b)
        interval = PercentileInterval(percentile)
        planes = []
        for c in (r, g, b):
            plane = _zeros_for(c, shape)
            scaled = interval(plane) if c is not None else plane
            planes.append(np.nan_to_num(np.clip(scaled, 0.0, 1.0)))
        rgb = np.stack(planes, axis=2)
        return (rgb * 255).astype(np.uint8)

    return combine


def _normalize(plane: np.ndarray) -> np.ndarray:
    """Min-max normalize a plane to [0, 1] (constant planes map to zeros)."""
    finite = plane[np.isfinite(plane)]
    if finite.size == 0:
        return np.zeros_like(plane)
    lo, hi = float(finite.min()), float(finite.max())
    if hi <= lo:
        return np.zeros_like(plane)
    return np.clip((np.nan_to_num(plane, nan=lo) - lo) / (hi - lo), 0.0, 1.0)


def combine_image_data(
    data: ImageData,
    mapping: Mapping[str, str | None],
    combiner: Combiner,
) -> RGBImage:
    """Combine an ImageData's stacked per-filter frames into an :class:`RGBImage`.

    :param data: the (stacked) working data; each mapped filter must hold exactly
        one frame.
    :param mapping: channel name (``"red"``/``"green"``/``"blue"``) -> filter name
        (or ``None`` to leave that channel black).
    :param combiner: the configured combine algorithm.
    :returns: the combined :class:`RGBImage`, carrying the mapping used.
    :raises ValueError: if a mapped filter is absent or not yet stacked (i.e. does
        not hold exactly one frame), or if mapped channels disagree in shape.
    """
    planes: dict[str, np.ndarray | None] = {}
    resolved: dict[str, str | None] = {}
    for channel in CHANNELS:
        filt = mapping.get(channel)
        resolved[channel] = filt
        if filt is None:
            planes[channel] = None
            continue
        frames = data.lights.get(filt)
        if not frames:
            raise ValueError(f"channel {channel!r} mapped to unknown filter {filt!r}")
        if len(frames) != 1:
            raise ValueError(
                f"filter {filt!r} is not stacked yet ({len(frames)} frames); "
                f"stack before colour combination"
            )
        planes[channel] = np.asarray(frames[0].data, dtype=float)

    rgb = combiner(planes["red"], planes["green"], planes["blue"])
    return RGBImage(data=rgb, mapping=resolved)
