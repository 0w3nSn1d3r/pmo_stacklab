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


def render_png(
    frame: CCDData,
    *,
    stretch: str = "asinh",
    intensity: float = 0.5,
    max_side: int = DEFAULT_MAX_SIDE,
) -> bytes:
    """Render one frame to a display-stretched grayscale PNG.

    :param frame: the stored frame to visualize (never modified).
    :param stretch: display-stretch name -- ``"asinh"``, ``"log"``, ``"sqrt"``, or
        ``"linear"``. Use ``"linear"`` for already-display-ready data (Post-Process
        output) to show it exactly as produced.
    :param intensity: faint-signal-boost knob in [0, 1] (ignored by linear/sqrt).
    :param max_side: longest-side cap for the downsample.
    :returns: PNG-encoded bytes (8-bit grayscale).
    """
    small = downsample(np.asarray(frame.data, dtype=float), max_side)

    # Normalize+clip to [0, 1] on the display copy, then apply the display stretch.
    normalized = PercentileInterval(_DISPLAY_PERCENTILE)(small)
    shown = _make_stretch(stretch, intensity)(normalized)

    # Off-grid/masked pixels (e.g. from reprojection) survive as NaN; zero them so
    # the image encodes, then scale [0,1] -> 8-bit.
    shown = np.nan_to_num(np.clip(shown, 0.0, 1.0), nan=0.0)
    u8 = (shown * 255).astype(np.uint8)

    buffer = io.BytesIO()
    Image.fromarray(u8, mode="L").save(buffer, format="PNG")
    return buffer.getvalue()
