"""Algorithm registry and process definition for the Reproject process.

Declares Reproject's two subprocesses -- registration (how each frame's mapping to
the reference is estimated) and alignment (how the frame is then resampled) -- as
:class:`Subprocess` objects, and assembles them into the :data:`REPROJECT`
:class:`ProcessSpec`. The registration options deliberately span a quality
spectrum (identity, translation-only, star-matching, WCS) so their results can be
juxtaposed; the alignment options span interpolation quality.
"""
from __future__ import annotations

from ..core import (
    Algorithm,
    ChoiceParam,
    FloatParam,
    IntParam,
    ProcessSpec,
    Subprocess,
)
from .align import build_warp
from .register import (
    build_astroalign,
    build_none,
    build_phase_correlation,
    build_wcs,
)
from .reproject import reproject_coordinator

REGISTRATION = Subprocess(
    name="registration",
    label="Registration",
    description=(
        "Estimate how each frame maps onto the reference frame, without yet moving "
        "any pixels. Compare the methods: more capable ones correct rotation and "
        "scale, not just shift."
    ),
    algorithms=(
        Algorithm(
            name="none",
            label="None (assume aligned)",
            description="Apply no registration; treat the frames as already aligned.",
            builder=build_none,
        ),
        Algorithm(
            name="astroalign",
            label="Star Matching (astroalign)",
            description=(
                "Match star asterisms between frames to solve for shift, rotation, "
                "and scale. Robust and needs no WCS; the general-purpose choice."
            ),
            builder=build_astroalign,
            parameters=(
                FloatParam(
                    name="detection_sigma",
                    default=5.0,
                    minimum=1.0,
                    maximum=20.0,
                    step=0.5,
                    description="Star-detection threshold in background sigmas.",
                ),
            ),
        ),
        Algorithm(
            name="phase_correlation",
            label="Phase Correlation (translation only)",
            description=(
                "FFT cross-correlation that solves for translation only. Fast, but "
                "cannot correct field rotation -- useful for seeing where simpler "
                "methods break down."
            ),
            builder=build_phase_correlation,
            parameters=(
                IntParam(
                    name="upsample_factor",
                    default=1,
                    minimum=1,
                    maximum=100,
                    description="Sub-pixel refinement: shifts resolved to 1/this px.",
                ),
            ),
        ),
        Algorithm(
            name="wcs",
            label="WCS Solution",
            description=(
                "Derive the mapping from each frame's astrometric (WCS) solution. "
                "Accurate when a WCS is present, but raw frames often lack one."
            ),
            builder=build_wcs,
        ),
    ),
)

ALIGNMENT = Subprocess(
    name="alignment",
    label="Alignment",
    description=(
        "Resample each frame onto the reference grid using the registration "
        "mapping. The interpolation kernel trades sharpness against ringing."
    ),
    algorithms=(
        Algorithm(
            name="bilinear",
            label="Bilinear",
            description="Smooth interpolation with mild blurring; a safe default.",
            builder=lambda: build_warp("bilinear"),
        ),
        Algorithm(
            name="nearest",
            label="Nearest Neighbour",
            description=(
                "Copy the closest pixel; introduces no new values but looks blocky."
            ),
            builder=lambda: build_warp("nearest"),
        ),
        Algorithm(
            name="bicubic",
            label="Bicubic",
            description=(
                "Sharper than bilinear, but can overshoot (ring) near bright edges."
            ),
            builder=lambda: build_warp("bicubic"),
        ),
    ),
)

#: The Reproject process: registration then alignment, applied per filter by the
#: Reproject coordinator (see :func:`reproject_coordinator`).
REPROJECT = ProcessSpec(
    name="Reproject",
    subprocesses=(REGISTRATION, ALIGNMENT),
    coordinator=reproject_coordinator,
)
