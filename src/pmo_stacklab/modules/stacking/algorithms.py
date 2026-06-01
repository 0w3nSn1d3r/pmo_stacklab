"""Algorithm registry and process definition for the Stack process.

Declares, as data, the algorithms the user may choose for Stack's two
subprocesses -- outlier rejection and coaddition -- by wrapping the cube-reducing
builders in this package as :class:`Algorithm` / :class:`Subprocess` objects with
typed parameter schemas, and assembles them into the :data:`STACK`
:class:`ProcessSpec`. These declarations are what the generalized endpoint builds
operators from, and what the frontend renders (via ``to_dict``).

Each algorithm's ``builder`` returns a Stack ``CubeOperator`` (a function of one
frame cube); the generalized builder neither knows nor cares about that shape.
Where an underlying builder takes a non-scalar argument (winsorize's percentile
pair), a small adapter maps the flat, individually-typed parameters onto it -- the
per-algorithm "argument parser" the architecture calls for.
"""
from __future__ import annotations

from ..core import Algorithm, FloatParam, ProcessSpec, Subprocess
from .coaddition import Coaddition
from .outlier_filters import OutlierFilters
from .stack import no_rejection, stack_coordinator

# NOTE: Coaddition.build_ivw_mean is not registered yet -- it needs the bias frames
# as a call-time side input, which the cube-operator model does not yet supply.

OUTLIER_REJECTION = Subprocess(
    name="outlier_rejection",
    label="Outlier Rejection",
    description=(
        "Mask deviant pixels across the frame stack -- cosmic rays, satellite "
        "trails, and hot pixels that survived calibration -- before coaddition."
    ),
    algorithms=(
        Algorithm(
            name="none",
            label="None",
            description="Apply no rejection; every pixel is coadded.",
            builder=lambda: no_rejection,
        ),
        Algorithm(
            name="sigma_clip",
            label="Sigma Clip",
            description=(
                "Iteratively mask pixels lying more than `sigma` robust standard "
                "deviations from the per-pixel median."
            ),
            builder=OutlierFilters.build_sigma_clip,
            parameters=(
                FloatParam(
                    name="sigma",
                    default=3.0,
                    minimum=0.0,
                    maximum=10.0,
                    step=0.1,
                    description="Clipping threshold in standard deviations.",
                ),
            ),
        ),
        Algorithm(
            name="winsorize",
            label="Winsorize",
            description=(
                "Replace pixels beyond the given lower/upper percentiles with the "
                "nearest surviving value, rather than masking them."
            ),
            # Adapter: the underlying builder takes a single (lower, upper) pair.
            builder=lambda lower, upper: OutlierFilters.build_winsorize((lower, upper)),
            parameters=(
                FloatParam(
                    name="lower",
                    default=0.05,
                    minimum=0.0,
                    maximum=0.5,
                    step=0.01,
                    description="Lower-tail fraction to winsorize (0-0.5).",
                ),
                FloatParam(
                    name="upper",
                    default=0.05,
                    minimum=0.0,
                    maximum=0.5,
                    step=0.01,
                    description="Upper-tail fraction to winsorize (0-0.5).",
                ),
            ),
        ),
        Algorithm(
            name="percentile_clip",
            label="Percentile Clip",
            description=(
                "Mask, per pixel, any frame value below the lower or above the upper "
                "percentile across the stack. Unlike sigma clip this uses fixed "
                "percentile cuts rather than the data's spread."
            ),
            # Adapter: the underlying builder takes a single (lower, upper) pair, in
            # percent (0-100).
            builder=lambda lower, upper: OutlierFilters.build_percentile_clip((lower, upper)),
            parameters=(
                FloatParam(
                    name="lower",
                    default=5.0,
                    minimum=0.0,
                    maximum=50.0,
                    step=0.5,
                    description="Lower percentile cut (0-50).",
                ),
                FloatParam(
                    name="upper",
                    default=95.0,
                    minimum=50.0,
                    maximum=100.0,
                    step=0.5,
                    description="Upper percentile cut (50-100).",
                ),
            ),
        ),
    ),
)

COADDITION = Subprocess(
    name="coaddition",
    label="Coaddition",
    description="Combine the surviving pixels at each position into one value.",
    algorithms=(
        Algorithm(
            name="median",
            label="Median",
            description="Per-pixel median across frames; robust, slightly noisier.",
            builder=Coaddition.build_median,
        ),
        Algorithm(
            name="mean",
            label="Mean",
            description="Per-pixel mean across frames; lowest noise, less robust.",
            builder=Coaddition.build_mean,
        ),
        Algorithm(
            name="biweight",
            label="Biweight Mean",
            description=(
                "Robust biweight location: a tunable compromise between mean and "
                "median that smoothly down-weights outliers."
            ),
            builder=Coaddition.build_biweight_mean,
            parameters=(
                FloatParam(
                    name="c",
                    default=6.0,
                    minimum=1.0,
                    maximum=12.0,
                    step=0.5,
                    description="Tuning constant; smaller rejects harder (typical 4-8).",
                ),
            ),
        ),
    ),
)

#: The Stack process: outlier rejection then coaddition, collapsed per filter by
#: the Stack coordinator (see :func:`stack_coordinator`).
STACK = ProcessSpec(
    name="Stack",
    subprocesses=(OUTLIER_REJECTION, COADDITION),
    coordinator=stack_coordinator,
)
