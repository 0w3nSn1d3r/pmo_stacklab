"""RGBImage -- the terminal colour result of combining per-filter frames.

Colour combination is the one operation that breaks the per-filter-grayscale
invariant of :class:`~pmo_stacklab.modules.core.image_data.ImageData`: it maps
several single-filter frames onto the red/green/blue channels of one picture. To
keep that invariant intact, the result is NOT folded back into ImageData; it is
this distinct, terminal object instead.

An RGBImage holds the three channel planes (already combined to 8-bit display
values, since colour is an endpoint for viewing) plus the filter-to-channel
mapping that produced it, so the UI can show "R <- Halpha, G <- OIII, ..." and a
PNG can be encoded directly.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

#: The three channel names, in array order (axis 2 of the RGB data).
CHANNELS = ("red", "green", "blue")


@dataclass(frozen=True)
class RGBImage:
    """A combined colour image: an (H, W, 3) uint8 array plus its channel mapping.

    :param data: the colour image as an ``(H, W, 3)`` ``uint8`` array (R, G, B).
    :param mapping: which filter fed each channel, e.g.
        ``{"red": "R", "green": "G", "blue": "B"}``; a channel with no assigned
        filter maps to ``None`` and is black.
    """

    data: np.ndarray
    mapping: dict[str, str | None]

    @property
    def shape(self) -> tuple[int, int]:
        """The image's ``(height, width)`` in pixels."""
        return (int(self.data.shape[0]), int(self.data.shape[1]))
