"""Registry declaration for the colour-combine algorithms.

Colour combination is not a pipeline process, but its combine *algorithm* is still
declared as a :class:`Subprocess` so the methods are selectable and parameterized
through the same registry mechanism (and schema JSON) as everything else. The
colour endpoint builds the chosen combiner from this and pairs it with the user's
channel->filter mapping.
"""
from __future__ import annotations

from .color_combine import build_linear, build_lupton
from .parameters import FloatParam
from .registry import Algorithm, Subprocess

COLOR_COMBINE = Subprocess(
    name="combine",
    label="Colour Combine",
    description=(
        "Combine the per-filter stacked frames assigned to the red/green/blue "
        "channels into a single colour image."
    ),
    algorithms=(
        Algorithm(
            name="lupton",
            label="Lupton asinh",
            description=(
                "The standard astronomical colour-combine: an asinh stretch applied "
                "across the channels together, so bright star cores keep their "
                "colour instead of saturating to white."
            ),
            builder=build_lupton,
            parameters=(
                FloatParam(
                    name="stretch",
                    default=5.0,
                    minimum=0.1,
                    maximum=50.0,
                    step=0.1,
                    description="Linear span mapped through the asinh; larger shows fainter signal.",
                ),
                FloatParam(
                    name="Q",
                    default=8.0,
                    minimum=0.1,
                    maximum=30.0,
                    step=0.1,
                    description="Asinh softening; larger keeps bright cores from washing out.",
                ),
            ),
        ),
        Algorithm(
            name="linear",
            label="Linear (per channel)",
            description=(
                "Normalize each channel independently by a percentile clip. The "
                "simple, literal mapping -- contrast it with Lupton's joint asinh."
            ),
            builder=build_linear,
            parameters=(
                FloatParam(
                    name="percentile",
                    default=99.5,
                    minimum=50.0,
                    maximum=100.0,
                    step=0.1,
                    description="Central percentage kept when setting each channel's white point.",
                ),
            ),
        ),
    ),
)
