"""The Stack process: integrate many calibrated, registered light frames into one.

Stack is the pipeline step where each filter's light frames collapse from N
frames to a single integrated frame. Its two subprocesses are:

* outlier rejection -- mask deviant pixels across the frame stack (cosmic rays,
  satellite trails, hot pixels that survived calibration); and
* coaddition -- combine the surviving pixels into one value per position.

Unlike the linear processes, Stack does not apply its operators one after another
to the ImageData. Instead its coordinator COMPOSES them into a single
frame-combining function and hands that to :meth:`ImageData.collapse_lights`, so
the N->1 pixel collapse and the metadata merge happen together, per filter, in a
single call.

The operators here are "cube" reducers: they act on a 3-D NumPy array whose first
axis is the frame index (the shape the rejection/coaddition algorithm builders in
this package produce). The coordinator turns the container's per-frame ``CCDData``
lists into that cube; :meth:`ImageData.collapse_lights` then wraps the combined
plane back into a ``CCDData`` with merged metadata.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np
from astropy.nddata import CCDData

from ..core import ImageData, Process

#: A Stack operator acts on a frame cube stacked along axis 0. Rejection
#: operators return a (masked) cube of the same shape; the coaddition operator
#: returns a single 2-D plane.
CubeOperator = Callable[[np.ndarray], np.ndarray]


def _stack_to_cube(frames: Sequence[CCDData]) -> np.ma.MaskedArray:
    """Stack frames' pixel data and masks into a masked cube (axis 0 = frame index).

    Per-frame masks set by earlier steps are carried into the cube so that
    rejection and coaddition ignore already-masked pixels.
    """
    data = np.stack([np.asarray(frame.data) for frame in frames])
    masks = [
        frame.mask if frame.mask is not None
        else np.zeros(np.shape(frame.data), dtype=bool)
        for frame in frames
    ]
    return np.ma.masked_array(data, mask=np.stack(masks))


def no_rejection(cube: np.ndarray) -> np.ndarray:
    """Identity outlier filter -- the "no rejection" option (pass the stack through)."""
    return cube


def stack_coordinator(operators: Sequence[CubeOperator], data: ImageData) -> ImageData:
    """Coordinate Stack: compose rejection + coaddition, then collapse per filter.

    The two operators are composed into one ``combine`` callable that turns a
    filter's frames into a single integrated plane, and that callable is handed to
    :meth:`ImageData.collapse_lights`, which applies it per filter and merges the
    metadata via the active metadata policy. Because the collapse is a single
    call, the pixel and metadata reductions stay in lock-step.

    :param operators: a 2-tuple ``(outlier_filter, coaddition)``. ``outlier_filter``
        masks deviant pixels across the stack (pass :func:`no_rejection` to skip
        rejection); ``coaddition`` reduces the stack to one plane.
    :param data: the working data, each filter holding the frames to integrate.
    :returns: a new ImageData in which every filter holds a single integrated frame.
    """
    outlier_filter, coaddition = operators

    def combine(frames: Sequence[CCDData]) -> np.ndarray:
        cube = _stack_to_cube(frames)
        return coaddition(outlier_filter(cube))

    return data.collapse_lights(combine)


def build_stack(
    outlier_filter: CubeOperator, coaddition: CubeOperator
) -> Process[CubeOperator]:
    """Build the Stack :class:`Process` from chosen rejection and coaddition algorithms.

    :param outlier_filter: a configured rejection algorithm (e.g. from
        :class:`~pmo_stacklab.modules.stacking.outlier_filters.OutlierFilters`);
        pass :func:`no_rejection` to skip rejection.
    :param coaddition: a configured coaddition algorithm (e.g. from
        :class:`~pmo_stacklab.modules.stacking.coaddition.Coaddition`).
    :returns: a Stack process ready to ``run`` on an :class:`ImageData`.
    """
    return Process(
        name="Stack",
        operators=(outlier_filter, coaddition),
        coordinator=stack_coordinator,
    )
