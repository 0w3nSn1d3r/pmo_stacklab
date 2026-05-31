"""The Reproject process: register the frames, then resample them onto one grid.

Reproject's two subprocesses are register (estimate each frame's mapping to the
reference) and align (resample with that mapping). They are deliberately kept
separate so a student can vary registration quality and resampling quality
independently and watch each one's effect.

Like Stack, Reproject is not a plain ``sequential`` fold: the register operator
produces per-frame transforms that the align operator must consume. Rather than
route those transforms through the ImageData keystone, the custom
:func:`reproject_coordinator` holds them locally and applies align frame-by-frame
-- so the inter-subprocess data (the transforms) never pollutes the container,
matching how the Stack coordinator composes its two operators internally.
"""
from __future__ import annotations

from collections.abc import Sequence

from ..core import ImageData, Process
from .align import AlignOp
from .register import RegisterOp

# Reproject's operators are heterogeneous (a register op then an align op), so the
# process is generic over ``object`` and the coordinator unpacks them positionally
# -- the same pattern the Stack process uses for its (rejection, coaddition) pair.
ReprojectOp = object


def reproject_coordinator(
    operators: Sequence[ReprojectOp], data: ImageData
) -> ImageData:
    """Coordinate Reproject: run register to get transforms, then align with them.

    :param operators: a 2-tuple ``(register, align)``. ``register`` maps the
        working data to per-filter, per-frame inverse maps; ``align`` resamples one
        frame given one inverse map.
    :param data: the working light frames to reproject.
    :returns: a new ImageData whose frames are all resampled onto their filter's
        reference grid (frame 0 of each filter).
    """
    register: RegisterOp = operators[0]  # type: ignore[assignment]
    align: AlignOp = operators[1]  # type: ignore[assignment]

    transforms = register(data)
    aligned = {
        filt: tuple(
            align(frame, transforms[filt][index])
            for index, frame in enumerate(frames)
        )
        for filt, frames in data.lights.items()
    }
    return data.with_lights(aligned)


def build_reproject(register: RegisterOp, align: AlignOp) -> Process[ReprojectOp]:
    """Build the Reproject :class:`Process` from chosen register and align algorithms.

    :param register: a configured registration operator (from
        :mod:`pmo_stacklab.modules.reprojection.register`).
    :param align: a configured alignment operator (from
        :mod:`pmo_stacklab.modules.reprojection.align`).
    :returns: a Reproject process ready to ``run`` on an :class:`ImageData`.
    """
    return Process(
        name="Reproject",
        operators=(register, align),
        coordinator=reproject_coordinator,
    )
