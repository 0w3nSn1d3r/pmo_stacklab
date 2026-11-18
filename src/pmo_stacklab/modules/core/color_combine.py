"""Colour combination: give each filter a colour, mix them, and tone-map the result.

This is a terminal, parallel operation rather than a pipeline ``Process``: its
input is the per-filter dict of stacked frames (not a single ImageData transform)
and its output is an :class:`RGBImage`, so it lives outside the generalized
``/api/run`` flow. It still reuses the algorithm registry for the *combine*
algorithm, so the methods are juxtaposable like everywhere else.

The assignment is **filter -> colour**, not a fixed red/green/blue triple. Real
filter sets are not RGB: a narrowband set has no green frame, an LRGB set has
four, a survey set may have six. Naming a colour per filter handles any number of
filters uniformly, and ordinary RGB is simply three filters given the three
primaries. It also expresses palettes that a channel mapping cannot: assigning
OIII a single cyan says "this filter is cyan" directly, where the channel model
had to smuggle the same filter into both green and blue.

Combination therefore happens in two stages, and the split matters:

1. **Mix** (here). Every contributing filter's frame is normalized to a common
   scale (:func:`normalize_plane`) and added into the red/green/blue accumulators
   in proportion to its colour. Each accumulator is divided by the total colour
   weight it received, so a channel is the *mean* of the filters feeding it --
   which keeps two filters sharing a colour from doubling that channel's
   brightness.
2. **Tone-map** (the combine algorithm). The mixed channels are turned into 8-bit
   display values. Normalizing per *filter* in stage 1 rather than per *channel*
   here is what makes the colour assignment meaningful: an algorithm that rescaled
   each channel independently would undo the very weighting that carries the
   colour.

PMO StackLab only coordinates established methods for the tone-map:

* ``lupton`` -- astropy's Lupton et al. asinh RGB, the standard astronomical
  colour-combine: an asinh stretch applied across the channels together so bright
  star cores keep their colour instead of saturating to white.
* ``linear`` -- a single shared white point, no curve; the literal mapping,
  useful to contrast with Lupton's joint asinh.

A filter may additionally be named as the *luminance*, in which case its
lightness is transplanted into the finished image (see
:mod:`pmo_stacklab.modules.core.luminance`) -- the LRGB technique.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping

import numpy as np
from astropy.visualization import make_lupton_rgb

from .image_data import ImageData
from .luminance import LuminanceOp
from .rgb_image import CHANNELS, RGBImage

# A combine algorithm tone-maps three mixed, normalized channel planes (each a
# 2-D float array, sky near 0 and structure near 1) into an (H, W, 3) uint8 RGB
# array. Unlike the planes it receives, its output is display-ready.
Combiner = Callable[[np.ndarray, np.ndarray, np.ndarray], np.ndarray]

# A normalizer puts one filter's frame on the common scale the mix stage needs:
# background near 0, bright structure near 1, the tail left open above. Which
# landmarks it anchors on is a user choice -- see the NORMALIZATION subprocess.
Normalizer = Callable[[np.ndarray], np.ndarray]

#: Percentile taken as "bright structure" -- the top of the reference span
#: :func:`normalize_plane` scales by. Deliberately not the maximum, which is a
#: saturated star core.
_HIGH_PERCENTILE = 99.5

#: Where every filter's sky background is placed on the normalized scale. Small
#: but non-zero: at exactly 0 half the background noise would clip to black,
#: taking the faintest real signal with it.
_SKY_LEVEL = 0.05


def parse_color(value: object) -> tuple[float, float, float]:
    """Parse a ``#rrggbb`` (or ``#rgb``) colour into RGB weights in [0, 1].

    :param value: the colour string, with or without the leading ``#``.
    :returns: the colour as ``(r, g, b)`` weights.
    :raises ValueError: if the value is not a hex colour.
    """
    if not isinstance(value, str):
        raise ValueError(f"colour must be a hex string like '#ff8800', got {value!r}")
    text = value.strip().lstrip("#")
    if len(text) == 3:  # shorthand: #abc -> #aabbcc
        text = "".join(ch * 2 for ch in text)
    if len(text) != 6:
        raise ValueError(f"colour must be a hex string like '#ff8800', got {value!r}")
    try:
        channels = tuple(int(text[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
    except ValueError:
        raise ValueError(
            f"colour must be a hex string like '#ff8800', got {value!r}"
        ) from None
    return channels  # type: ignore[return-value]


def _rescale(
    plane: np.ndarray, low: float, high: float, pedestal: float
) -> np.ndarray:
    """Map ``low`` -> ``pedestal`` and ``high`` -> 1, floored at 0, open above.

    Values above ``high`` are intentionally left greater than 1 rather than
    clipped: compressing that bright tail is precisely the asinh stretch's job,
    and clipping here would flatten every star core to white.
    """
    if high <= low:
        # Degenerate span (e.g. a uniform frame): nothing meaningful to scale.
        return np.zeros_like(plane)
    scaled = pedestal + (np.nan_to_num(plane, nan=low) - low) / (high - low) * (
        1.0 - pedestal
    )
    return np.clip(scaled, 0.0, None)


def build_sky_normalizer(
    sky_level: float = _SKY_LEVEL, high: float = _HIGH_PERCENTILE
) -> Normalizer:
    """Pin each frame's sky background to a fixed level (background neutralization).

    Anchored on two measured landmarks: the frame's **sky background**, pinned to
    ``sky_level``, and a high percentile taken as bright structure, pinned to 1.
    Pinning the sky is what neutralizes colour, and it is why normalization is
    done per filter -- every filter's background lands on the same value whatever
    its depth, throughput, or sky brightness.

    Contrast :func:`build_percentile_normalizer`, which leaves the sky floating
    at a height that depends on each frame's noise relative to its own range.

    The sky estimate is the median, which assumes background dominates the frame
    -- true of essentially any wide-field image, but worth knowing if a target
    ever fills most of the field.

    :param sky_level: where the background lands on the normalized scale. Small
        but non-zero by default: at exactly 0 half the background noise clips to
        black, taking the faintest real signal with it.
    :param high: percentile taken as bright structure.
    """

    def normalize(plane: np.ndarray) -> np.ndarray:
        finite = plane[np.isfinite(plane)]
        if finite.size == 0:
            return np.zeros_like(plane)
        return _rescale(
            plane,
            float(np.median(finite)),
            float(np.percentile(finite, high)),
            sky_level,
        )

    return normalize


def build_percentile_normalizer(
    low: float = 1.0, high: float = _HIGH_PERCENTILE
) -> Normalizer:
    """Anchor the scale on a low and a high percentile of each frame.

    Robust to outliers, but it does NOT neutralize the background: how far the
    sky then floats above black depends on the frame's noise relative to its own
    dynamic range, which differs per filter. On real M33 data the R frame's sky
    landed at 0.313 of its range while V and B sat at ~0.11, so the combined
    background came out three times too red -- the effect
    :func:`build_sky_normalizer` removes, and worth seeing next to it.

    :param low: percentile mapped to black.
    :param high: percentile taken as bright structure.
    """

    def normalize(plane: np.ndarray) -> np.ndarray:
        finite = plane[np.isfinite(plane)]
        if finite.size == 0:
            return np.zeros_like(plane)
        return _rescale(
            plane,
            float(np.percentile(finite, low)),
            float(np.percentile(finite, high)),
            0.0,
        )

    return normalize


def build_minmax_normalizer() -> Normalizer:
    """Scale by the frame's own minimum and maximum -- the naive baseline.

    Instructive because it fails plainly: the maximum of a real frame is a
    saturated star core, so dividing by it crushes everything else into a sliver
    just above zero (a 16-bit frame with a 65535 star and a ~250 ADU sky puts the
    sky at ~0.004) and the image renders essentially black at any stretch.
    """

    def normalize(plane: np.ndarray) -> np.ndarray:
        finite = plane[np.isfinite(plane)]
        if finite.size == 0:
            return np.zeros_like(plane)
        return _rescale(plane, float(finite.min()), float(finite.max()), 0.0)

    return normalize


def normalize_plane(plane: np.ndarray) -> np.ndarray:
    """Normalize one plane with the default (sky-pinned) settings."""
    return build_sky_normalizer()(plane)


def apply_gain(plane: np.ndarray, gain: float) -> np.ndarray:
    """Scale a normalized plane's signal by ``gain``, holding its background put.

    The gain acts on the distance from the background, NOT on the raw values: a
    plain multiply would scale the background pedestal too, so turning a filter
    up would drag its sky with it and re-tint the very thing normalization just
    neutralized. Rescaling about the background changes how strongly the filter
    contributes to *structure* while leaving the sky where the normalizer put it.

    The background is re-measured as the median of the normalized plane, so this
    works for whichever normalizer produced it.

    :param plane: a normalized plane.
    :param gain: multiplier for signal above the background; 1.0 is unchanged.
    """
    if gain == 1.0:
        return plane
    background = float(np.median(plane[np.isfinite(plane)])) if plane.size else 0.0
    return np.clip(background + (plane - background) * gain, 0.0, None)


def build_lupton(stretch: float = 0.5, Q: float = 8.0) -> Combiner:
    """Lupton asinh RGB tone-map (astropy ``make_lupton_rgb``).

    The channels are stretched *together*, from their shared intensity, so a
    bright star's colour survives instead of every core washing out to white.

    :param stretch: the linear span mapped through the asinh, in units of the
        normalized scale (1.0 is "bright structure"); larger shows fainter signal
        but flattens contrast.
    :param Q: the asinh softening; larger holds bright cores further back.
    """

    def combine(r: np.ndarray, g: np.ndarray, b: np.ndarray) -> np.ndarray:
        return make_lupton_rgb(r, g, b, stretch=stretch, Q=Q)

    return combine


def build_linear(percentile: float = 99.5) -> Combiner:
    """Linear tone-map against a single white point shared by all three channels.

    The white point is one percentile of the mixed data as a whole, not one per
    channel: a per-channel white point would rescale the channels relative to one
    another and so partly undo the colour assignment.

    :param percentile: percentile of the mixed data taken as the white point;
        lower clips more of the bright end and brightens the midtones.
    """

    def combine(r: np.ndarray, g: np.ndarray, b: np.ndarray) -> np.ndarray:
        stack = np.stack([r, g, b], axis=2)
        finite = stack[np.isfinite(stack)]
        white = float(np.percentile(finite, percentile)) if finite.size else 1.0
        if white <= 0.0:
            white = 1.0
        scaled = np.clip(np.nan_to_num(stack) / white, 0.0, 1.0)
        return (scaled * 255).astype(np.uint8)

    return combine


def mix_colors(
    planes: Mapping[str, np.ndarray],
    colors: Mapping[str, str],
    gains: Mapping[str, float] | None = None,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Mix normalized filter planes into red/green/blue accumulators by colour.

    Each channel is the colour-weighted *mean* of the filters contributing to it,
    so assigning two filters the same colour does not make that channel twice as
    bright. A channel no filter contributes to is left black.

    :param planes: filter name -> that filter's normalized plane.
    :param colors: filter name -> its ``#rrggbb`` colour.
    :param gains: optional filter name -> signal multiplier (see
        :func:`apply_gain`); filters absent from it are used unchanged. This is
        the colour-balance control: normalization equalizes the *backgrounds*,
        and the gains set how strongly each filter's *signal* registers.
    :returns: the three mixed ``(H, W)`` float planes, in :data:`CHANNELS` order.
    :raises ValueError: if a colour cannot be parsed.
    """
    shape = next(iter(planes.values())).shape
    accumulated = [np.zeros(shape, dtype=float) for _ in CHANNELS]
    weights = [0.0 for _ in CHANNELS]

    for filt, plane in planes.items():
        gained = apply_gain(plane, float((gains or {}).get(filt, 1.0)))
        weight = parse_color(colors[filt])
        for index, channel_weight in enumerate(weight):
            if channel_weight:
                accumulated[index] += gained * channel_weight
                weights[index] += channel_weight

    for index, total in enumerate(weights):
        if total > 0:
            accumulated[index] /= total
    return accumulated[0], accumulated[1], accumulated[2]


def combine_image_data(
    data: ImageData,
    colors: Mapping[str, str],
    combiner: Combiner,
    *,
    normalizer: Normalizer | None = None,
    gains: Mapping[str, float] | None = None,
    luminance_filter: str | None = None,
    luminance: LuminanceOp | None = None,
) -> RGBImage:
    """Combine an ImageData's stacked per-filter frames into an :class:`RGBImage`.

    :param data: the (stacked) working data; each named filter must hold exactly
        one frame.
    :param colors: filter name -> the ``#rrggbb`` colour it is given. Any number
        of filters may contribute; a filter absent from the mapping is ignored.
    :param combiner: the configured tone-map algorithm.
    :param normalizer: how to put each filter on the common scale; defaults to
        :func:`build_sky_normalizer` with its own defaults.
    :param gains: optional filter -> signal multiplier, the colour-balance
        control (see :func:`mix_colors`).
    :param luminance_filter: filter whose lightness to transplant into the
        result, or ``None`` to keep the colours' own lightness.
    :param luminance: the configured luminance operator. Both this and
        ``luminance_filter`` must be given for luminance to be applied.
    :returns: the combined :class:`RGBImage`, carrying the assignment used.
    :raises ValueError: if no filter is assigned a colour, if a named filter is
        absent or not yet stacked (i.e. does not hold exactly one frame), if a
        colour is malformed, or if the frames disagree in shape.
    """
    if not colors:
        raise ValueError("at least one filter must be assigned a colour")

    # Parse every colour up front so a malformed one fails before any pixel work.
    for filt, color in colors.items():
        parse_color(color)

    normalize = normalizer or build_sky_normalizer()
    planes = {
        filt: normalize(_frame_data(data, f"filter {filt!r}", filt))
        for filt in colors
    }
    shapes = {plane.shape for plane in planes.values()}
    if len(shapes) > 1:
        raise ValueError(
            f"the assigned filters have mismatched shapes: {sorted(shapes)}. "
            f"Reproject them onto a common grid first."
        )

    rgb = combiner(*mix_colors(planes, colors, gains))

    # Luminance is applied to the finished colour image, so every combine
    # algorithm gains it for free.
    if luminance is not None and luminance_filter is not None:
        plane = _frame_data(data, "luminance", luminance_filter)
        if plane.shape != rgb.shape[:2]:
            raise ValueError(
                f"luminance filter {luminance_filter!r} has shape {plane.shape}, "
                f"which does not match the colour filters' {rgb.shape[:2]}"
            )
        rgb = luminance(rgb, normalize(plane))
    else:
        luminance_filter = None

    return RGBImage(data=rgb, colors=dict(colors), luminance=luminance_filter)


def _frame_data(data: ImageData, label: str, filt: str) -> np.ndarray:
    """Return the single stacked frame's pixels for ``filt``.

    :raises ValueError: if the filter is absent from the data, or still holds more
        than one frame (i.e. has not been stacked).
    """
    frames = data.lights.get(filt)
    if not frames:
        raise ValueError(f"{label} is not among the available filters")
    if len(frames) != 1:
        raise ValueError(
            f"filter {filt!r} is not stacked yet ({len(frames)} frames); "
            f"stack before colour combination"
        )
    return np.asarray(frames[0].data, dtype=float)
