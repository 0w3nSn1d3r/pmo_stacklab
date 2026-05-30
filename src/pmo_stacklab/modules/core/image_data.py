"""The ImageData container -- the single data structure threaded through every
pipeline step.

ImageData is the project's answer to a hard truth about stacking: the data that
flows through the pipeline is not one image but a *collection* of frames whose
cardinality changes (calibration takes N lights in and N out; stacking takes N
in and 1 out) and whose four roles (light/dark/bias/flat) have different
lifetimes and groupings. Rather than subclass astropy's ``CCDData`` and bolt on
extra dimensions -- which breaks down because each frame has its own WCS and
header -- ImageData *composes* a collection of ``CCDData`` objects, so every
frame keeps its own data, WCS, header, mask, and uncertainty right up until the
moment of collapse.

Contract for the wider pipeline:

* Every subprocess has the shape ``f(image_data, params) -> image_data``.
* ImageData is **immutable**: transforms return a NEW instance that shares
  references to the frame sets they did not touch. This is what makes the
  per-step output cache (keyed by config-hash) and the before/after preview
  "blink" sound, and what lets the user re-run an earlier step cleanly.
* Light and flat frames are grouped **by filter**; darks and bias are not (they
  are filter-independent). Mono and one-shot-colour data simply land under a
  single default filter key, so the structure is uniform regardless of setup.
* The N->1 collapse of data and metadata happens in a single call
  (:meth:`ImageData.collapse_lights` / :meth:`ImageData.master`), so the pixel
  and metadata collapses can never fall out of step.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from collections.abc import Sequence, Mapping, Callable

import numpy as np
from astropy.nddata import CCDData

from .metadata_policy import MetadataPolicy

# Frames with no FILTER header (mono cameras, one-shot-colour sensors) are
# grouped under this key so the per-filter structure is uniform regardless of
# how the data was acquired.
DEFAULT_FILTER = "NONE"


def group_by_filter(frames: Sequence[CCDData]) -> dict[str, tuple[CCDData, ...]]:
    """Group frames by their FITS ``FILTER`` header value.

    :param frames: light or flat frames to group.
    :returns: a mapping of filter name -> the frames taken through that filter,
        preserving input order within each group. Frames lacking a ``FILTER``
        keyword are grouped under :data:`DEFAULT_FILTER`.
    """
    grouped: dict[str, list[CCDData]] = {}
    for frame in frames:
        filt = frame.header.get("FILTER", DEFAULT_FILTER)
        grouped.setdefault(filt, []).append(frame)
    return {filt: tuple(fs) for filt, fs in grouped.items()}


@dataclass(frozen=True)
class ImageData:
    """Immutable container for every frame flowing through the pipeline.

    Prefer :meth:`from_frames` to the bare constructor -- it groups lights and
    flats by filter for you. Treat every field as read-only and use the
    ``with_*`` / ``collapse_*`` / :meth:`master` transforms to derive new states.

    :param lights: the working light frames, grouped by filter. This is the set
        the pipeline operates on; it collapses to one frame per filter at Stack.
    :param darks: dark frames (filter-independent). Consumed during calibration.
    :param bias: bias frames (filter-independent). Consumed during calibration.
    :param flats: flat frames, grouped by filter. Consumed during calibration.
    :param policy: the metadata-reduction policy applied at every N->1 collapse.
    """

    lights: Mapping[str, tuple[CCDData, ...]]
    darks: tuple[CCDData, ...] = ()
    bias: tuple[CCDData, ...] = ()
    flats: Mapping[str, tuple[CCDData, ...]] = field(default_factory=dict)
    policy: MetadataPolicy = field(default_factory=MetadataPolicy)

    # -- construction ------------------------------------------------------

    @classmethod
    def from_frames(
        cls,
        lights: Sequence[CCDData],
        darks: Sequence[CCDData] = (),
        bias: Sequence[CCDData] = (),
        flats: Sequence[CCDData] = (),
        policy: MetadataPolicy | None = None,
    ) -> "ImageData":
        """Build an ImageData from flat sequences of frames.

        Lights and flats are grouped by filter automatically; darks and bias are
        stored as-is. This is the intended entry point at the Upload step and
        replaces the old ``folder2ccd`` dict.

        :param lights: all light frames (any mix of filters).
        :param darks: all dark frames.
        :param bias: all bias frames.
        :param flats: all flat frames (any mix of filters).
        :param policy: metadata-reduction policy; a default policy is used if
            omitted.
        :raises ValueError: if no light frames are supplied.
        """
        lights = tuple(lights)
        if not lights:
            raise ValueError("ImageData requires at least one light frame.")
        return cls(
            lights=group_by_filter(lights),
            darks=tuple(darks),
            bias=tuple(bias),
            flats=group_by_filter(tuple(flats)),
            policy=policy or MetadataPolicy(),
        )

    # -- introspection -----------------------------------------------------

    @property
    def filters(self) -> tuple[str, ...]:
        """The filter keys present in the light set, in insertion order."""
        return tuple(self.lights.keys())

    @property
    def is_stacked(self) -> bool:
        """True once every filter's light set has collapsed to a single frame."""
        return all(len(frames) == 1 for frames in self.lights.values())

    # -- functional transforms (each returns a new ImageData) --------------

    def with_lights(self, lights: Mapping[str, Sequence[CCDData]]) -> "ImageData":
        """Return a copy with the light set replaced; all other sets are shared.

        Used by per-frame steps (calibration, registration) that transform every
        light frame but leave the calibration sets untouched. The shared
        references make this cheap.
        """
        normalised = {filt: tuple(fs) for filt, fs in lights.items()}
        return replace(self, lights=normalised)

    def drop_calibration_frames(self) -> "ImageData":
        """Return a copy with the darks/bias/flats removed.

        Calibration consumes the calibration frames, so dropping them after the
        Calibrate step frees memory and keeps the container honest about what is
        still usable downstream.
        """
        return replace(self, darks=(), bias=(), flats={})

    # -- the atomic N->1 collapse -----------------------------------------

    def collapse_lights(
        self,
        combine: Callable[[Sequence[CCDData]], object],
        reference_index: int = 0,
    ) -> "ImageData":
        """Collapse each filter's light frames into a single combined frame.

        This is the Stack step's N->1 integration. For every filter, ``combine``
        reduces that filter's frames to one image (it owns the pixel combination),
        and the metadata policy independently merges the frames' headers/WCS; the
        two are stitched together so the pixel and metadata collapses stay in
        lock-step.

        :param combine: reduces a sequence of frames to one combined image. It
            may return a ``CCDData`` (preferred) or a bare/masked ``ndarray`` (in
            which case the unit is inherited from the reference frame and any
            uncertainty is dropped). The Stack coordinator builds this callable by
            composing the chosen outlier-rejection and coaddition algorithms.
        :param reference_index: index, within each filter group, of the frame
            supplying canonical metadata (e.g. the registration reference).
        :returns: a new ImageData in which every filter maps to a single frame
            (so :attr:`is_stacked` becomes True).
        """
        collapsed = {
            filt: (self._combine_group(frames, combine, reference_index),)
            for filt, frames in self.lights.items()
        }
        return replace(self, lights=collapsed)

    def master(
        self,
        frame_type: str,
        combine: Callable[[Sequence[CCDData]], object],
        filt: str | None = None,
        reference_index: int = 0,
    ) -> CCDData:
        """Build a master calibration frame from one of the calibration sets.

        Master-frame creation (many darks/bias/flats -> one master) is itself an
        N->1 collapse, so it reuses exactly the same data+metadata machinery as
        :meth:`collapse_lights`.

        :param frame_type: one of ``"darks"``, ``"bias"``, ``"flats"``.
        :param combine: reduces the frame set to one combined frame (same
            contract as in :meth:`collapse_lights`).
        :param filt: required for ``"flats"`` (which are per-filter); ignored for
            darks and bias.
        :param reference_index: index of the frame supplying canonical metadata.
        :returns: the combined master frame.
        :raises ValueError: for an unknown ``frame_type``, a missing filter on a
            flat, or an empty frame set.
        """
        if frame_type == "darks":
            frames = self.darks
        elif frame_type == "bias":
            frames = self.bias
        elif frame_type == "flats":
            if filt is None:
                raise ValueError("A filter must be given to build a master flat.")
            frames = self.flats.get(filt, ())
        else:
            raise ValueError(f"Unknown calibration frame type: {frame_type!r}")

        if not frames:
            raise ValueError(f"No {frame_type} frames available to combine.")
        return self._combine_group(frames, combine, reference_index)

    # -- internals ---------------------------------------------------------

    def _combine_group(
        self,
        frames: Sequence[CCDData],
        combine: Callable[[Sequence[CCDData]], object],
        reference_index: int,
    ) -> CCDData:
        """Combine one group of frames: pixels via ``combine``, metadata via the
        policy, stitched into a single CCDData.

        Tolerates ``combine`` returning either a ``CCDData`` or a (possibly
        masked) ``ndarray`` so it works both with library combiners and with the
        project's current array-returning coaddition builders.
        """
        combined = combine(frames)
        if isinstance(combined, CCDData):
            data, unit = combined.data, combined.unit
            mask, uncertainty = combined.mask, combined.uncertainty
        else:
            # Bare array (or masked array) -> inherit unit from the reference
            # frame and carry across any mask.
            data = np.ma.getdata(combined)
            mask = (
                np.ma.getmaskarray(combined)
                if np.ma.isMaskedArray(combined)
                else None
            )
            unit = frames[reference_index].unit
            uncertainty = None

        # The policy returns the merged metadata header and the canonical WCS as
        # a separate object (the CCDData constructor does not parse a WCS from
        # header keywords), with conflicting WCS keywords already stripped.
        header, wcs = self.policy.merge(frames, reference_index)
        return CCDData(
            data,
            unit=unit,
            mask=mask,
            uncertainty=uncertainty,
            meta=header,
            wcs=wcs,
        )
