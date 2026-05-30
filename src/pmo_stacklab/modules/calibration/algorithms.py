"""Algorithm registry and process definition for the Calibrate process.

Declares, as data, the algorithm the user may configure for each of Calibrate's
three subprocesses -- bias subtraction, dark subtraction, and flat fielding --
by wrapping the calibration operators in this package as :class:`Algorithm` /
:class:`Subprocess` objects with typed parameter schemas, and assembles them into
the :data:`CALIBRATE` :class:`ProcessSpec`.

Unlike Stack, each calibration step currently offers a single operation rather
than competing algorithms; the user-facing variation is in its parameters (e.g.
whether to scale the master dark by exposure time). Each algorithm's ``builder``
returns an ``ImageData -> ImageData`` operator -- a different callable shape from
Stack's cube reducers, which the generalized builder handles identically.

Master frames are built with the median combiner for now; offering the master
combination method as a choice (reusing the coaddition algorithms) is a noted
future enhancement.
"""
from __future__ import annotations

from ..core import Algorithm, BoolParam, ProcessSpec, Subprocess
from .calibrate import (
    bias_subtraction,
    calibrate_coordinator,
    dark_subtraction,
    flat_fielding,
    median_master,
)

BIAS_SUBTRACTION = Subprocess(
    name="bias_subtraction",
    label="Bias Subtraction",
    description="Subtract the master bias to remove the sensor's read offset.",
    algorithms=(
        Algorithm(
            name="subtract",
            label="Subtract Master Bias",
            description="Build a master bias (median) and subtract it from every light.",
            builder=lambda: bias_subtraction(median_master),
        ),
    ),
)

DARK_SUBTRACTION = Subprocess(
    name="dark_subtraction",
    label="Dark Subtraction",
    description="Subtract the master dark to remove thermal (dark-current) signal.",
    algorithms=(
        Algorithm(
            name="subtract",
            label="Subtract Master Dark",
            description="Build a master dark (median) and subtract it from every light.",
            builder=lambda scale: dark_subtraction(median_master, scale),
            parameters=(
                BoolParam(
                    name="scale",
                    default=True,
                    description=(
                        "Scale the master dark by the light/dark exposure-time ratio "
                        "before subtracting."
                    ),
                ),
            ),
        ),
    ),
)

FLAT_FIELDING = Subprocess(
    name="flat_fielding",
    label="Flat Fielding",
    description="Divide by the normalized master flat to correct vignetting and dust.",
    algorithms=(
        Algorithm(
            name="divide",
            label="Divide by Master Flat",
            description=(
                "Build a per-filter master flat (median), normalize it, and divide "
                "every light of that filter by it."
            ),
            builder=lambda: flat_fielding(median_master),
        ),
    ),
)

#: The Calibrate process: bias -> dark -> flat, applied to every light, after
#: which the calibration frames are dropped (see :func:`calibrate_coordinator`).
CALIBRATE = ProcessSpec(
    name="Calibrate",
    subprocesses=(BIAS_SUBTRACTION, DARK_SUBTRACTION, FLAT_FIELDING),
    coordinator=calibrate_coordinator,
)
