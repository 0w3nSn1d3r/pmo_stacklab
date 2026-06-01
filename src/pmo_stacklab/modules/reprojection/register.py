"""Registration algorithms: estimate how each frame maps onto a reference.

Registration is the first of Reproject's two subprocesses. It does NOT move
pixels; it only computes, for every light frame, the geometric mapping from the
reference frame's grid back to that frame -- an "inverse map" in the form skimage's
``warp`` consumes (output coordinate -> input coordinate). The second subprocess
(align) then resamples with that mapping, so the user can juxtapose registration
quality and resampling quality independently.

PMO StackLab does not implement registration math; it coordinates established
libraries and exposes their trade-offs:

* ``none`` -- identity; assume the frames are already aligned (the baseline that
  shows why registration matters).
* ``astroalign`` -- robust star-asterism matching (handles shift + rotation +
  scale); needs no WCS. The modern, general method.
* ``phase_correlation`` -- skimage FFT phase correlation; fast but
  translation-only, so it fails under field rotation -- a deliberate inferior
  juxtaposition.
* ``wcs`` -- derives the mapping from each frame's astrometric WCS solution;
  "correct" when a WCS exists, but raw frames often lack one.

Every algorithm yields the same uniform per-frame inverse-map callable, so the
align subprocess can apply them all identically. The reference is the first frame
of each filter (registration is per filter, matching per-filter stacking;
cross-filter alignment for colour is a future concern).
"""
from __future__ import annotations

from collections.abc import Callable, Mapping

import numpy as np
from skimage.registration import phase_cross_correlation

from ..core import ImageData, PipelineError

# A per-output-coordinate inverse map: given an (N, 2) array of (col, row)=(x, y)
# coordinates on the reference grid, return the corresponding (N, 2) coordinates
# in the source frame. This is exactly what skimage.transform.warp accepts as its
# ``inverse_map``; skimage SimilarityTransform.inverse and astroalign transforms
# satisfy it directly.
InverseMap = Callable[[np.ndarray], np.ndarray]

# Per-filter registration result: filter -> one inverse map per frame, in frame
# order. Passed from the register operator to the align operator by the Reproject
# coordinator.
TransformMap = Mapping[str, tuple[InverseMap, ...]]

# A register operator: reads the working data and returns the transforms to apply.
RegisterOp = Callable[[ImageData], TransformMap]


def _identity(coords: np.ndarray) -> np.ndarray:
    """Identity inverse map: output coordinates map to themselves."""
    return coords


def _per_filter(
    data: ImageData, make_map: Callable[[int, object, object], InverseMap]
) -> TransformMap:
    """Build a TransformMap by calling ``make_map(index, frame, reference)`` per frame.

    The reference is frame 0 of each filter and always receives the identity map;
    other frames receive whatever ``make_map`` computes.
    """
    transforms: dict[str, tuple[InverseMap, ...]] = {}
    for filt, frames in data.lights.items():
        reference = frames[0]
        maps: list[InverseMap] = []
        for index, frame in enumerate(frames):
            maps.append(_identity if index == 0 else make_map(index, frame, reference))
        transforms[filt] = tuple(maps)
    return transforms


def build_none() -> RegisterOp:
    """Identity registration: every frame maps to itself (assume pre-aligned)."""

    def register(data: ImageData) -> TransformMap:
        return {filt: tuple(_identity for _ in frames) for filt, frames in data.lights.items()}

    return register


def build_astroalign(detection_sigma: float = 5.0) -> RegisterOp:
    """Star-matching registration via astroalign.

    :param detection_sigma: source-detection threshold (in background sigmas)
        astroalign uses to find the stars it matches; lower finds fainter stars.
    """
    import astroalign  # imported lazily so the rest of the app need not load it

    def register(data: ImageData) -> TransformMap:
        def make_map(index: int, frame: object, reference: object) -> InverseMap:
            try:
                # find_transform(source, target) maps source -> target, so the
                # frame -> reference transform's INVERSE is reference -> frame,
                # exactly the inverse map warp needs.
                transform, _ = astroalign.find_transform(
                    frame.data, reference.data, detection_sigma=detection_sigma
                )
            except Exception as exc:
                raise PipelineError(
                    "Star-matching registration could not align a frame -- it "
                    "likely found too few matched stars. Try lowering the detection "
                    "threshold, or use a different registration method."
                ) from exc
            return transform.inverse

        return _per_filter(data, make_map)

    return register


def build_phase_correlation(upsample_factor: int = 1) -> RegisterOp:
    """Translation-only registration via skimage FFT phase correlation.

    :param upsample_factor: sub-pixel refinement factor; 1 is whole-pixel, higher
        values estimate shifts to 1/upsample_factor of a pixel.
    """

    def register(data: ImageData) -> TransformMap:
        def make_map(index: int, frame: object, reference: object) -> InverseMap:
            # phase_cross_correlation(reference, moving) returns the (row, col)
            # shift that registers `moving` to `reference`; the reference-grid
            # output coordinate p maps back to source coordinate p - shift.
            shift, _, _ = phase_cross_correlation(
                reference.data, frame.data, upsample_factor=upsample_factor
            )
            d_row, d_col = float(shift[0]), float(shift[1])

            # NB: this function must NOT be named ``inverse`` -- skimage.warp treats
            # a callable named ``inverse`` as a bound homography method and accesses
            # ``.__self__``, which a plain closure lacks. Any other name routes it
            # through warp's documented general-callable path.
            def inverse_map(coords: np.ndarray, d_row=d_row, d_col=d_col) -> np.ndarray:
                out = np.asarray(coords, dtype=float).copy()
                out[:, 0] -= d_col  # x = column
                out[:, 1] -= d_row  # y = row
                return out

            return inverse_map

        return _per_filter(data, make_map)

    return register


def build_wcs() -> RegisterOp:
    """WCS-based registration: derive the mapping from each frame's WCS solution."""

    def register(data: ImageData) -> TransformMap:
        def make_map(index: int, frame: object, reference: object) -> InverseMap:
            if reference.wcs is None or frame.wcs is None:
                raise PipelineError(
                    "WCS registration needs every frame to carry a WCS (astrometric) "
                    "solution, but some do not. Use star-matching registration "
                    "instead, or plate-solve the frames first."
                )
            return _wcs_inverse(reference.wcs, frame.wcs)

        return _per_filter(data, make_map)

    return register


def _wcs_inverse(reference_wcs: object, frame_wcs: object) -> InverseMap:
    """Inverse map taking reference pixel coords through world coords to frame pixels."""

    # Must not be named ``inverse`` (see the note in build_phase_correlation).
    def inverse_map(coords: np.ndarray) -> np.ndarray:
        coords = np.asarray(coords, dtype=float)
        world = reference_wcs.wcs_pix2world(coords, 0)
        return frame_wcs.wcs_world2pix(world, 0)

    return inverse_map
