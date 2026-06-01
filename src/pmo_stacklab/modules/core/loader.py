"""FITS loading -- construct the initial :class:`ImageData` from uploaded frames.

This is the honest replacement for the old ``folder2ccd``: it reads FITS frames
(from file paths or in-memory file-like objects) into ``CCDData`` and groups them,
by role, into the keystone :class:`ImageData` the rest of the pipeline consumes.

Reading is delegated to :meth:`astropy.nddata.CCDData.read`, which parses each
frame's WCS as an object and strips the WCS keywords from the header -- the
conflict-free invariant :class:`ImageData` and
:class:`~pmo_stacklab.modules.core.metadata_policy.MetadataPolicy` depend on. The
unit is taken from the frame's ``BUNIT`` keyword when present, falling back to
:data:`DEFAULT_UNIT` otherwise.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from astropy.nddata import CCDData

from .image_data import ImageData
from .metadata_policy import MetadataPolicy

#: Assumed pixel unit when a frame's header carries no ``BUNIT``. Raw sensor
#: counts are in analog-to-digital units, the universal default for stacking.
DEFAULT_UNIT = "adu"


def load_frame(source: Any, *, unit: str = DEFAULT_UNIT) -> CCDData:
    """Read a single FITS frame into a :class:`~astropy.nddata.CCDData`.

    :param source: a file path, or an in-memory binary file-like object (e.g. a
        ``BytesIO`` or an uploaded file's stream). The image HDU is located
        automatically, so both simple and multi-extension FITS are accepted.
    :param unit: pixel unit to assume when the frame has no ``BUNIT`` keyword;
        an explicit ``BUNIT`` in the file takes precedence.
    :returns: the frame as a CCDData, with its WCS parsed and header preserved.
    :raises ValueError: if ``source`` is not a readable FITS frame.

    ``format="fits"`` is passed explicitly: the app only accepts FITS, and
    astropy's content-based auto-identification is unreliable on the nameless
    multipart upload streams Werkzeug hands us (it raises "Format could not be
    identified"). Being explicit makes uploads from the browser form work
    regardless of how the stream presents itself.
    """
    try:
        return CCDData.read(source, unit=unit, format="fits")
    except Exception as exc:  # normalise astropy/OSError variety into one error type
        raise ValueError(f"could not read FITS frame: {exc}") from exc


def load_frames(
    sources: Iterable[Any], *, unit: str = DEFAULT_UNIT
) -> list[CCDData]:
    """Read many FITS frames into a list of CCDData (see :func:`load_frame`)."""
    return [load_frame(source, unit=unit) for source in sources]


def load_image_data(
    *,
    lights: Iterable[Any],
    darks: Iterable[Any] = (),
    bias: Iterable[Any] = (),
    flats: Iterable[Any] = (),
    unit: str = DEFAULT_UNIT,
    policy: MetadataPolicy | None = None,
) -> ImageData:
    """Read uploaded frames, by role, into the initial :class:`ImageData`.

    Lights and flats are grouped by filter inside :meth:`ImageData.from_frames`;
    darks and bias are filter-independent. At least one light frame is required.

    :param lights: light-frame sources (paths or file-like objects).
    :param darks: dark-frame sources.
    :param bias: bias-frame sources.
    :param flats: flat-frame sources.
    :param unit: pixel unit assumed when a frame lacks ``BUNIT``.
    :param policy: metadata-reduction policy for the session; a default is used if
        omitted.
    :returns: the initial ImageData for the pipeline.
    :raises ValueError: if a frame cannot be read, or if no lights are supplied.
    """
    return ImageData.from_frames(
        lights=load_frames(lights, unit=unit),
        darks=load_frames(darks, unit=unit),
        bias=load_frames(bias, unit=unit),
        flats=load_frames(flats, unit=unit),
        policy=policy,
    )
