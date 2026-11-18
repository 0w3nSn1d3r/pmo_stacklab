"""Luminance application -- lend a high-signal L frame's detail to the colour image.

The classic LRGB technique. Colour and detail carry very differently: chrominance
survives heavy binning and short exposures, while fine structure and faint signal
need depth. So observers shoot one deep, unfiltered (luminance/clear) frame for
detail and shorter R/G/B frames for hue, then transplant the L frame's lightness
into the colour image -- keeping the colour it already has.

That transplant is a *replacement of lightness only*, which means it must happen
in a space that separates lightness from hue and saturation; doing it in RGB
would change the colours. The two algorithms here are the two standard choices,
kept side by side so the difference is visible:

* ``lab`` -- CIE L*a*b*, whose L* axis is perceptually uniform and whose a*/b*
  axes carry chrominance independently. The colorimetrically correct choice, and
  the one that preserves hue most faithfully.
* ``hsv`` -- replace HSV's Value channel. Cruder (Value is not perceptual
  lightness, so equal-Value colours do not look equally bright) and it tends to
  look more saturated -- the instructive contrast to ``lab``.

Both take an ``amount`` so the L frame can be blended in rather than swapped
wholesale: a full replacement can look harsh and discards whatever real
brightness information the colour channels carried.

The operators receive the luminance plane already normalized to [0, 1] by
:func:`~pmo_stacklab.modules.core.color_combine.normalize_plane`, so they are
concerned only with the colour-space transplant.
"""
from __future__ import annotations

from collections.abc import Callable

import numpy as np
from skimage.color import hsv2rgb, lab2rgb, rgb2hsv, rgb2lab

#: A luminance operator: given the combined ``(H, W, 3)`` uint8 RGB image and a
#: ``(H, W)`` luminance plane normalized to [0, 1], return a new uint8 RGB image
#: carrying the luminance's lightness and the original's colour.
LuminanceOp = Callable[[np.ndarray, np.ndarray], np.ndarray]


def _to_uint8(rgb01: np.ndarray) -> np.ndarray:
    """Clip a float RGB image in [0, 1] back to the uint8 display range."""
    return (np.clip(np.nan_to_num(rgb01), 0.0, 1.0) * 255).astype(np.uint8)


def _blend(original: np.ndarray, replacement: np.ndarray, amount: float) -> np.ndarray:
    """Linearly mix ``replacement`` into ``original`` by ``amount`` in [0, 1]."""
    a = float(np.clip(amount, 0.0, 1.0))
    return (1.0 - a) * original + a * replacement


def build_lab(amount: float = 1.0) -> LuminanceOp:
    """Replace the image's CIE L* lightness with the luminance frame.

    The colorimetrically correct LRGB combine: converting to L*a*b* isolates
    perceptual lightness in L*, so substituting it leaves the a*/b* chrominance --
    and therefore the hue and saturation -- untouched.

    :param amount: how much of the L frame to take, 0 (ignore it) to 1 (replace
        lightness entirely).
    """

    def apply(rgb: np.ndarray, lum: np.ndarray) -> np.ndarray:
        lab = rgb2lab(np.asarray(rgb, dtype=float) / 255.0)
        # L* runs 0..100; the normalized luminance maps straight onto that axis.
        lab[..., 0] = _blend(lab[..., 0], np.clip(lum, 0.0, 1.0) * 100.0, amount)
        return _to_uint8(lab2rgb(lab))

    return apply


def build_hsv(amount: float = 1.0) -> LuminanceOp:
    """Replace the image's HSV Value with the luminance frame.

    The naive transplant, kept for contrast with :func:`build_lab`: Value is the
    maximum RGB component, not perceptual lightness, so equal-Value colours do
    not appear equally bright and the result usually looks more saturated.

    :param amount: how much of the L frame to take, 0 (ignore it) to 1 (replace
        Value entirely).
    """

    def apply(rgb: np.ndarray, lum: np.ndarray) -> np.ndarray:
        hsv = rgb2hsv(np.asarray(rgb, dtype=float) / 255.0)
        hsv[..., 2] = _blend(hsv[..., 2], np.clip(lum, 0.0, 1.0), amount)
        return _to_uint8(hsv2rgb(hsv))

    return apply
