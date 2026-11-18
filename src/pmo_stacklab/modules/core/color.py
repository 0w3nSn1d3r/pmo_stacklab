"""Registry declaration for the colour-combine algorithms.

Colour combination is not a pipeline process, but its algorithms are still
declared as :class:`Subprocess` objects so the methods are selectable and
parameterized through the same registry mechanism (and schema JSON) as everything
else. The colour endpoint builds the chosen combiner (and, when a filter is
assigned to luminance, the chosen luminance operator) from these and pairs them
with the user's channel->filter mapping.
"""
from __future__ import annotations

from .color_combine import (
    build_linear,
    build_lupton,
    build_minmax_normalizer,
    build_percentile_normalizer,
    build_sky_normalizer,
)
from .luminance import build_hsv, build_lab
from .parameters import FloatParam
from .registry import Algorithm, Subprocess

#: How each filter's frame is put on the common scale before the colours are
#: mixed. This is the step that decides whether the combined background comes out
#: neutral, so it is a user choice rather than a hidden preprocessing detail --
#: switching between these is the clearest way to see *why* a sky goes coloured.
NORMALIZATION = Subprocess(
    name="normalization",
    label="Channel Normalization",
    description=(
        "Put every filter on a common scale before mixing. Filters differ in "
        "depth, throughput and sky brightness, so what this anchors on decides "
        "whether the combined background is neutral or takes on the colour of "
        "whichever filter sat highest."
    ),
    default="sky",
    algorithms=(
        Algorithm(
            name="minmax",
            label="Min-Max",
            description=(
                "Scale by each frame's own minimum and maximum. The naive "
                "baseline, and it fails plainly: the maximum is a saturated star "
                "core, so everything else is crushed to near-black."
            ),
            builder=build_minmax_normalizer,
        ),
        Algorithm(
            name="percentile",
            label="Percentile",
            description=(
                "Anchor on a low and a high percentile. Robust to hot pixels, but "
                "it does not neutralize the background: how far each sky floats "
                "above black depends on that frame's noise relative to its own "
                "range, which is what tints a combined image."
            ),
            builder=build_percentile_normalizer,
            parameters=(
                FloatParam(
                    name="low",
                    default=1.0,
                    minimum=0.0,
                    maximum=20.0,
                    step=0.1,
                    description="Percentile mapped to black.",
                ),
                FloatParam(
                    name="high",
                    default=99.5,
                    minimum=95.0,
                    maximum=99.99,
                    step=0.05,
                    description="Percentile taken as bright structure.",
                ),
            ),
        ),
        Algorithm(
            name="sky",
            label="Sky-Pinned (neutral background)",
            description=(
                "Pin every frame's measured sky background to the same level, so "
                "the combined background is neutral by construction whatever the "
                "filters' depths. The standard background neutralization."
            ),
            builder=build_sky_normalizer,
            parameters=(
                FloatParam(
                    name="sky_level",
                    default=0.05,
                    minimum=0.0,
                    maximum=0.3,
                    step=0.01,
                    description=(
                        "Where the background sits on the scale. At 0 half the "
                        "sky noise clips to black; higher lifts the background."
                    ),
                ),
                FloatParam(
                    name="high",
                    default=99.5,
                    minimum=95.0,
                    maximum=99.99,
                    step=0.05,
                    description="Percentile taken as bright structure.",
                ),
            ),
        ),
    ),
)

COLOR_COMBINE = Subprocess(
    name="combine",
    label="Colour Combine",
    description=(
        "Turn the colour-mixed channels into a display image. Each filter's frame "
        "is already normalized and mixed according to the colour you gave it; this "
        "chooses the transfer curve applied to the result."
    ),
    default="lupton",
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
                    default=0.3,
                    minimum=0.05,
                    maximum=2.0,
                    step=0.05,
                    description=(
                        "Signal level mapped to full brightness, where 1.0 is bright "
                        "structure; smaller shows fainter signal."
                    ),
                ),
                FloatParam(
                    name="Q",
                    default=8.0,
                    minimum=1.0,
                    maximum=20.0,
                    step=0.5,
                    description="Asinh softening; larger keeps bright cores from washing out.",
                ),
            ),
        ),
        Algorithm(
            name="linear",
            label="Linear",
            description=(
                "No curve: scale against one white point shared by all channels. "
                "The literal mapping -- contrast it with Lupton's joint asinh, which "
                "compresses the bright end."
            ),
            builder=build_linear,
            parameters=(
                FloatParam(
                    name="percentile",
                    default=99.5,
                    minimum=95.0,
                    maximum=99.9,
                    step=0.05,
                    description=(
                        "Percentile of the mixed data taken as the white point; "
                        "lower brightens the midtones and clips more highlights."
                    ),
                ),
            ),
        ),
    ),
)

#: How a filter assigned to the luminance channel is applied. Declared as its own
#: Subprocess because it is an independent choice from the combine algorithm: the
#: luminance is transplanted into whatever colour image the combiner produced.
LUMINANCE_APPLY = Subprocess(
    name="luminance",
    label="Luminance",
    description=(
        "Transplant the lightness of the filter assigned to luminance into the "
        "colour image (the LRGB technique), keeping the colour the channels give. "
        "Only used when a filter is assigned to luminance."
    ),
    default="lab",
    algorithms=(
        Algorithm(
            name="lab",
            label="CIE L*a*b*",
            description=(
                "Replace perceptual lightness (L*) while leaving the a*/b* "
                "chrominance untouched -- the colorimetrically correct LRGB "
                "combine, and the most faithful to the original hues."
            ),
            builder=build_lab,
            parameters=(
                FloatParam(
                    name="amount",
                    default=1.0,
                    minimum=0.0,
                    maximum=1.0,
                    step=0.05,
                    description="How much of the luminance frame to take; 1 replaces lightness entirely.",
                ),
            ),
        ),
        Algorithm(
            name="hsv",
            label="HSV Value",
            description=(
                "Replace HSV's Value channel. Cruder than L*a*b* -- Value is not "
                "perceptual lightness -- and usually looks more saturated."
            ),
            builder=build_hsv,
            parameters=(
                FloatParam(
                    name="amount",
                    default=1.0,
                    minimum=0.0,
                    maximum=1.0,
                    step=0.05,
                    description="How much of the luminance frame to take; 1 replaces Value entirely.",
                ),
            ),
        ),
    ),
)
