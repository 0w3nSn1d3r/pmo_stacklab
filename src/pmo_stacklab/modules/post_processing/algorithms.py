"""Algorithm registry and process definition for the Post-Process process.

Declares Post-Process's three (grayscale, per-filter) subprocesses -- background
modeling, intensity scaling, and stretch -- as :class:`Subprocess` objects, and
assembles them into the :data:`POST_PROCESS` :class:`ProcessSpec`.

The subprocess order (background -> intensity-scaling -> stretch) is technical as
well as pedagogical: background subtraction works on linear data, intensity
scaling normalizes to [0, 1], and the stretch transfer functions assume that
[0, 1] input. Colour mapping is intentionally absent (a deferred later unit).
"""
from __future__ import annotations

from ..core import Algorithm, FloatParam, IntParam, ProcessSpec, Subprocess, sequential
from . import background_modeling, intensity_scaling, stretch

BACKGROUND = Subprocess(
    name="background",
    label="Background Modeling",
    description=(
        "Estimate and subtract the sky background so light-pollution gradients and "
        "vignetting do not dominate the stretched image."
    ),
    algorithms=(
        Algorithm(
            name="none",
            label="None",
            description="Subtract no background (baseline).",
            builder=background_modeling.build_none,
        ),
        Algorithm(
            name="global",
            label="Global Median",
            description=(
                "Subtract a single constant (the median sky level); removes an "
                "overall pedestal but not gradients."
            ),
            builder=background_modeling.build_global,
        ),
        Algorithm(
            name="sep_2d",
            label="2-D Model (sep)",
            description=(
                "Subtract a smoothly varying 2-D background from Source Extractor "
                "(sep); removes gradients and vignetting."
            ),
            builder=background_modeling.build_sep_2d,
            parameters=(
                IntParam(
                    name="box_size",
                    default=64,
                    minimum=8,
                    maximum=256,
                    description="Mesh box size (px) for the background estimate.",
                ),
            ),
        ),
    ),
)

INTENSITY_SCALING = Subprocess(
    name="intensity_scaling",
    label="Intensity Scaling",
    description=(
        "Pick the black and white points and normalize to [0, 1]. This sets how "
        "aggressively shadows and highlights are clipped before the stretch."
    ),
    algorithms=(
        Algorithm(
            name="percentile",
            label="Percentile Clip",
            description=(
                "Keep the central percentage of values (clipping the tails); robust "
                "to a few hot pixels."
            ),
            builder=intensity_scaling.build_percentile,
            parameters=(
                FloatParam(
                    name="percentile",
                    default=99.0,
                    minimum=50.0,
                    maximum=100.0,
                    step=0.1,
                    description="Central percentage of pixels to keep.",
                ),
            ),
        ),
        Algorithm(
            name="zscale",
            label="ZScale",
            description=(
                "The IRAF ZScale algorithm; picks limits well for high-dynamic-range "
                "astronomical images."
            ),
            builder=intensity_scaling.build_zscale,
            parameters=(
                FloatParam(
                    name="contrast",
                    default=0.25,
                    minimum=0.05,
                    maximum=1.0,
                    step=0.05,
                    description="ZScale contrast; smaller raises apparent contrast.",
                ),
            ),
        ),
        Algorithm(
            name="minmax",
            label="Min-Max",
            description="Use the data's own min and max; no clipping.",
            builder=intensity_scaling.build_minmax,
        ),
    ),
)

STRETCH = Subprocess(
    name="stretch",
    label="Stretch",
    description=(
        "Apply a non-linear transfer function that boosts faint signal relative to "
        "bright stars -- the step that reveals nebulosity. Compare the curves."
    ),
    algorithms=(
        Algorithm(
            name="asinh",
            label="Asinh",
            description=(
                "Inverse hyperbolic sine; brightens faint signal while holding bright "
                "stars back. The popular, well-behaved choice."
            ),
            builder=stretch.build_asinh,
            parameters=(
                FloatParam(
                    name="a",
                    default=0.1,
                    minimum=0.01,
                    maximum=1.0,
                    step=0.01,
                    description="Linear/log transition point; smaller boosts faint signal more.",
                ),
            ),
        ),
        Algorithm(
            name="log",
            label="Logarithmic",
            description="Strong faint-end boost; tunable contrast.",
            builder=stretch.build_log,
            parameters=(
                FloatParam(
                    name="a",
                    default=1000.0,
                    minimum=10.0,
                    maximum=10000.0,
                    step=10.0,
                    description="Contrast; larger compresses the bright end harder.",
                ),
            ),
        ),
        Algorithm(
            name="sqrt",
            label="Square Root",
            description="Mild faint-end boost.",
            builder=stretch.build_sqrt,
        ),
        Algorithm(
            name="linear",
            label="Linear",
            description="No non-linear compression (baseline; shows why a stretch helps).",
            builder=stretch.build_linear,
        ),
    ),
)

#: The Post-Process process: background -> intensity-scaling -> stretch, applied
#: per filter. Linear, so it uses the shared ``sequential`` coordinator.
POST_PROCESS = ProcessSpec(
    name="Post-Process",
    subprocesses=(BACKGROUND, INTENSITY_SCALING, STRETCH),
    coordinator=sequential,
)
