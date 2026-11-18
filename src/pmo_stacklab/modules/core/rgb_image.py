"""RGBImage -- the terminal colour result of combining per-filter frames.

Colour combination is the one operation that breaks the per-filter-grayscale
invariant of :class:`~pmo_stacklab.modules.core.image_data.ImageData`: it maps
several single-filter frames onto one three-channel picture. To keep that
invariant intact, the result is NOT folded back into ImageData; it is this
distinct, terminal object instead.

An RGBImage holds the combined 8-bit display image (colour is an endpoint for
viewing) plus the *assignment* that produced it: the colour given to each
contributing filter, and the filter -- if any -- whose lightness was transplanted
in. That is what lets the UI report "Ha -> #ff2200, OIII -> #00ffcc" and what the
FITS export records.

The assignment is a filter -> colour mapping rather than a fixed red/green/blue
triple because real filter sets are not RGB. A narrowband set has no "green"
frame; an LRGB set has four; a survey set may have six. Naming a colour per
filter covers all of them uniformly, and the familiar RGB case is just the
special case of three filters assigned the three primaries.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

import numpy as np

#: The three output channel names, in array order (axis 2 of the RGB data). These
#: are the *output* planes, not user-facing assignments -- filters are assigned
#: arbitrary colours, which are mixed down into these three.
CHANNELS = ("red", "green", "blue")


@dataclass(frozen=True)
class RGBImage:
    """A combined colour image: an (H, W, 3) uint8 array plus its assignment.

    :param data: the colour image as an ``(H, W, 3)`` ``uint8`` array (R, G, B).
    :param colors: the filters that contributed and the colour each was given, as
        ``{"Ha": "#ff0000", "OIII": "#00ffff"}``. A filter absent from this
        mapping did not contribute.
    :param luminance: the filter whose lightness was transplanted into the
        result, or ``None`` if the colours' own lightness was kept.
    """

    data: np.ndarray
    colors: Mapping[str, str] = field(default_factory=dict)
    luminance: str | None = None

    @property
    def shape(self) -> tuple[int, int]:
        """The image's ``(height, width)`` in pixels."""
        return (int(self.data.shape[0]), int(self.data.shape[1]))
