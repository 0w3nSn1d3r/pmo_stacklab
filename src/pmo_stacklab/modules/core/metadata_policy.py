"""Metadata-reduction policy for collapsing many frames into one.

When the pipeline combines N frames into a single image -- stacking light frames,
or building a master dark/bias/flat -- the pixel data collapses N -> 1, but so
does the *metadata*: N FITS headers and N WCS solutions must become one. That
collapse is lossy and the "right" answer is a judgement call (which ``DATE-OBS``
survives? is ``EXPTIME`` the sum or the mean?), so it is expressed as an
explicit, user-configurable policy rather than hard-coded deep in the stacking
math.

A :class:`MetadataPolicy` is built from the standardized JSON the GUI submits
(exactly as the algorithms are) and is applied by
:class:`~pmo_stacklab.modules.core.image_data.ImageData` at every collapse point,
so the data collapse and the metadata collapse always happen together and can
never drift out of sync.
"""
from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Sequence

from astropy.io.fits import Header
from astropy.nddata import CCDData
from astropy.wcs import WCS


@dataclass(frozen=True)
class MetadataPolicy:
    """Rules for merging the headers and WCS of N frames into one.

    Frozen/immutable so a policy can be shared safely across cached pipeline
    states. Build one per session from the user's submitted configuration.

    :param exptime: how to combine ``EXPTIME`` across the frames -- ``"sum"``
        (total integration time, the usual choice for an integrated stack),
        ``"mean"``, or ``"first"`` (keep the seed frame's value).
    :param dateobs: which ``DATE-OBS`` to keep -- ``"first"``, ``"last"``, or
        ``"min"`` (earliest; ISO-8601 timestamps sort chronologically).
    :param wcs: whose WCS becomes canonical -- ``"reference"`` (the frame at the
        ``reference_index`` passed to :meth:`merge`, valid once frames share a
        common grid after registration) or ``"first"``.

    The defaults (sum exposure, earliest date, reference WCS) match the common
    case of integrating registered light frames. Add new rules here as
    subprocesses need them; any keyword not governed by a rule is inherited
    unchanged from the seed frame.
    """

    exptime: str = "sum"
    dateobs: str = "first"
    wcs: str = "reference"

    def merge(
        self, frames: Sequence[CCDData], reference_index: int = 0
    ) -> tuple[Header, WCS | None]:
        """Merge the metadata of ``frames`` into a single header and WCS.

        The header is seeded as a copy of the header of whichever frame the
        ``wcs`` rule designates as canonical (so its instrument/target keywords
        are retained), then the policy-controlled keywords are overwritten. The
        canonical WCS is returned **separately, as an object**, because the
        ``CCDData`` constructor does not parse a WCS out of header keywords -- and
        any WCS keywords still present in the header are stripped so they cannot
        conflict with that object when both are handed to ``CCDData``.

        :param frames: the frames being collapsed, in pipeline order. Must be
            non-empty.
        :param reference_index: index of the frame supplying the canonical WCS
            under the ``"reference"`` rule (e.g. the registration reference).
        :returns: a ``(header, wcs)`` pair for the combined frame. ``wcs`` is
            ``None`` if the chosen frame carries no WCS.
        """
        wcs_index = reference_index if self.wcs == "reference" else 0
        ref = frames[wcs_index]
        header = ref.header.copy()

        # EXPTIME: combine exposure across the stack per the configured rule.
        exptimes = [f.header["EXPTIME"] for f in frames if "EXPTIME" in f.header]
        if exptimes:
            if self.exptime == "sum":
                header["EXPTIME"] = sum(exptimes)
            elif self.exptime == "mean":
                header["EXPTIME"] = sum(exptimes) / len(exptimes)
            # "first" -> leave the seed frame's value untouched.

        # DATE-OBS: choose a single timestamp to represent the combined frame.
        dates = [f.header["DATE-OBS"] for f in frames if "DATE-OBS" in f.header]
        if dates:
            if self.dateobs == "first":
                header["DATE-OBS"] = dates[0]
            elif self.dateobs == "last":
                header["DATE-OBS"] = dates[-1]
            elif self.dateobs == "min":
                header["DATE-OBS"] = min(dates)

        # Take the canonical WCS as an object, and remove any matching WCS
        # keywords from the header so CCDData(meta=header, wcs=wcs) won't raise on
        # a header/WCS conflict.
        wcs = ref.wcs
        if wcs is not None:
            # `del` works whether the header is a fits.Header or a plain dict.
            for key in wcs.to_header(relax=True):
                if key in header:
                    del header[key]

        return header, wcs
