"""Preview rendering: turn a stored frame into a small, display-stretched PNG.

This is the pedagogy's visual half. A frame as stored in the pipeline is full-
resolution *linear* data: for every step up to Stack it looks nearly black to the
eye, because the interesting signal occupies a tiny fraction of the value range.
To show it, the preview applies a *display* transform -- downsample for size, then
a normalize+stretch for visibility -- and encodes a PNG.

Crucial invariant: this transform is applied only to a COPY rendered for the
screen. The stored frame is never modified, so the original linear data still
flows through the pipeline (no double-stretching) and remains available for the
metrics, which must be computed on linear data, not on this display copy.

The display stretch is the user's choice in the preview panel (stretch type +
intensity), entirely separate from any stretch the Post-Process step applies to
the real data. Post-Process output is already display-ready, so callers render it
with ``stretch="linear"`` to show it exactly as produced.
"""
from __future__ import annotations

import io

import numpy as np
from astropy.nddata import CCDData
from astropy.visualization import (
    AsinhStretch,
    LinearStretch,
    LogStretch,
    ManualInterval,
    PercentileInterval,
    SqrtStretch,
)
from PIL import Image

#: Default cap on the longest side of a preview, in pixels. Display-only; metrics
#: are computed on full-resolution data, so downsampling never affects the numbers.
DEFAULT_MAX_SIDE = 1024

#: Percentile interval used to set the display black/white points before stretching.
_DISPLAY_PERCENTILE = 99.5


def _make_stretch(stretch: str, intensity: float):
    """Map a display-stretch name + intensity (0-1) to an astropy stretch object.

    ``intensity`` is a single intuitive knob: higher means more faint-signal boost.
    It is mapped onto each stretch's natural parameter; ``linear`` and ``sqrt``
    ignore it (they take no parameter).
    """
    if stretch == "linear":
        return LinearStretch()
    if stretch == "sqrt":
        return SqrtStretch()
    if stretch == "asinh":
        # asinh 'a' in (0, 1]; smaller boosts faint signal more, so invert intensity.
        a = float(np.clip(1.0 - intensity, 0.01, 1.0))
        return AsinhStretch(a=a)
    if stretch == "log":
        # log 'a' larger -> stronger boost; map intensity onto a log scale 10..10000.
        a = float(10.0 ** (1.0 + 3.0 * np.clip(intensity, 0.0, 1.0)))
        return LogStretch(a=a)
    raise ValueError(f"unknown display stretch {stretch!r}")


def downsample(data: np.ndarray, max_side: int = DEFAULT_MAX_SIDE) -> np.ndarray:
    """Block-mean downsample so the longest side is <= ``max_side``.

    Block-mean (rather than striding) avoids aliasing in the preview. Purely a
    display convenience; the stored data is untouched.
    """
    data = np.asarray(data, dtype=float)
    height, width = data.shape
    factor = max(1, int(np.ceil(max(height, width) / max_side)))
    if factor == 1:
        return data
    trimmed_h, trimmed_w = (height // factor) * factor, (width // factor) * factor
    block = data[:trimmed_h, :trimmed_w].reshape(
        trimmed_h // factor, factor, trimmed_w // factor, factor
    )
    return block.mean(axis=(1, 3))


def _crop_region(
    data: np.ndarray, region: tuple[float, float, float, float]
) -> np.ndarray:
    """Crop ``data`` to a fractional ``region`` = (x0, y0, x1, y1), each in [0, 1].

    Fractions (rather than pixels) let the caller select a region from the preview
    without knowing the full-resolution shape or downsample factor. The region is
    clamped to the image and guaranteed at least one pixel in each axis.
    """
    height, width = data.shape
    x0f, y0f, x1f, y1f = region
    x0, x1 = sorted((x0f, x1f))
    y0, y1 = sorted((y0f, y1f))
    col0 = int(np.clip(np.floor(x0 * width), 0, width - 1))
    row0 = int(np.clip(np.floor(y0 * height), 0, height - 1))
    col1 = int(np.clip(np.ceil(x1 * width), col0 + 1, width))
    row1 = int(np.clip(np.ceil(y1 * height), row0 + 1, height))
    return data[row0:row1, col0:col1]


def render_png(
    frame: CCDData,
    *,
    stretch: str = "asinh",
    intensity: float = 0.5,
    max_side: int = DEFAULT_MAX_SIDE,
    region: tuple[float, float, float, float] | None = None,
) -> bytes:
    """Render one frame (or a region of it) to a display-stretched grayscale PNG.

    The black/white points (the percentile interval) are computed on the WHOLE
    frame and reused for any region, so a zoomed-in tile keeps the overview's
    brightness mapping -- a crop never looks artificially brighter or darker than
    the full view. This is the same matched-display honesty rule the blink uses.

    :param frame: the stored frame to visualize (never modified).
    :param stretch: display-stretch name -- ``"asinh"``, ``"log"``, ``"sqrt"``, or
        ``"linear"``. Use ``"linear"`` for already-display-ready data (Post-Process
        output) to show it exactly as produced.
    :param intensity: faint-signal-boost knob in [0, 1] (ignored by linear/sqrt).
    :param max_side: longest-side cap for the downsample.
    :param region: optional fractional crop ``(x0, y0, x1, y1)`` in [0, 1]; when
        given, the returned image is that region of the full-resolution frame
        (still downsampled only if it exceeds ``max_side``), so it shows more
        detail than the same area in the full-frame overview.
    :returns: PNG-encoded bytes (8-bit grayscale).
    """
    full = np.asarray(frame.data, dtype=float)

    # Fix the black/white points on the full frame so overview and crops match.
    interval = PercentileInterval(_DISPLAY_PERCENTILE)
    vmin, vmax = interval.get_limits(full)

    selected = _crop_region(full, region) if region is not None else full
    small = downsample(selected, max_side)

    # Apply the shared limits, then the display stretch.
    normalized = ManualInterval(vmin, vmax)(small)
    shown = _make_stretch(stretch, intensity)(normalized)

    # Off-grid/masked pixels (e.g. from reprojection) survive as NaN; zero them so
    # the image encodes, then scale [0,1] -> 8-bit.
    shown = np.nan_to_num(np.clip(shown, 0.0, 1.0), nan=0.0)
    u8 = (shown * 255).astype(np.uint8)

    buffer = io.BytesIO()
    Image.fromarray(u8, mode="L").save(buffer, format="PNG")
    return buffer.getvalue()
