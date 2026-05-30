"""The Calibrate process: remove the instrument signature from the light frames.

Calibration corrects each light frame for the camera's additive and
multiplicative artefacts using sets of calibration frames:

* bias subtraction -- remove the sensor's per-pixel read offset;
* dark subtraction -- remove thermal signal (scaled to the light's exposure); and
* flat fielding -- divide out vignetting and dust shadows (per filter).

Each step is an ``ImageData -> ImageData`` operator that builds the master frame
it needs from the container's calibration sets (via :meth:`ImageData.master`) and
applies it to every light frame. The Calibrate coordinator runs the chosen
operators in order and then drops the now-consumed calibration frames, so the
container that leaves Calibrate honestly holds only calibrated lights.

Master frames are built with an injectable combiner (default: per-pixel median),
keeping the *how* of master creation swappable -- the GUI's algorithm choices
will supply it through the registry. Because calibration changes only pixel
values (not astrometry or timing), each transformed light is produced by copying
the source frame and replacing its data, which preserves the frame's WCS,
header, mask, and uncertainty exactly.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np
from astropy.nddata import CCDData

from ..core import ImageData, Operator, Process

#: Builds one master frame from a set of calibration frames. Same contract as the
#: ``combine`` argument of :meth:`ImageData.master`: frames in, one combined frame
#: (a CCDData or a bare ndarray) out.
FrameCombiner = Callable[[Sequence[CCDData]], CCDData | np.ndarray]


def median_master(frames: Sequence[CCDData]) -> np.ndarray:
    """Default master-frame combiner: the per-pixel median across the frames."""
    cube = np.ma.masked_array([np.asarray(frame.data, dtype=float) for frame in frames])
    return np.ma.median(cube, axis=0)


def _with_data(frame: CCDData, new_data: np.ndarray) -> CCDData:
    """Copy ``frame`` but replace its pixel data, preserving WCS/header/mask/unit.

    Calibration alters only pixel values, so copying the frame and swapping its
    data is the faithful way to carry every other attribute through unchanged.
    (CCDData's arithmetic methods drop the WCS, so they are deliberately avoided.)
    """
    out = frame.copy()
    out.data = np.asarray(new_data, dtype=float)
    return out


def _map_lights(
    data: ImageData, transform: Callable[[CCDData], CCDData]
) -> ImageData:
    """Return a copy of ``data`` with ``transform`` applied to every light frame."""
    new_lights = {
        filt: tuple(transform(frame) for frame in frames)
        for filt, frames in data.lights.items()
    }
    return data.with_lights(new_lights)


def bias_subtraction(combine: FrameCombiner = median_master) -> Operator:
    """Build a bias-subtraction operator.

    Subtracts a master bias (built from the container's bias frames with
    ``combine``) from every light frame. No-ops if there are no bias frames.

    :param combine: how to combine the bias frames into the master bias.
    :returns: an ``ImageData -> ImageData`` calibration operator.
    """

    def operator(data: ImageData) -> ImageData:
        if not data.bias:
            return data
        master = np.asarray(data.master("bias", combine).data, dtype=float)
        return _map_lights(
            data, lambda f: _with_data(f, np.asarray(f.data, dtype=float) - master)
        )

    return operator


def dark_subtraction(
    combine: FrameCombiner = median_master, scale: bool = True
) -> Operator:
    """Build a dark-subtraction operator.

    Subtracts a master dark (built from the container's dark frames) from every
    light. When ``scale`` is true, the master dark is scaled by the ratio of the
    light's exposure to the darks' exposure before subtraction, so darks taken at
    a different exposure still apply correctly. No-ops if there are no dark frames.

    :param combine: how to combine the dark frames into the master dark.
    :param scale: scale the master dark by the EXPTIME ratio before subtracting.
    :returns: an ``ImageData -> ImageData`` calibration operator.
    """

    def operator(data: ImageData) -> ImageData:
        if not data.darks:
            return data
        master = np.asarray(data.master("darks", combine).data, dtype=float)
        # Read the dark exposure from a raw dark frame, NOT the master: the
        # metadata policy stamps the master with a *summed* EXPTIME (correct for a
        # light stack, wrong for an averaged master), so it must not be used here.
        dark_exptime = data.darks[0].header.get("EXPTIME") if scale else None

        def transform(frame: CCDData) -> CCDData:
            factor = 1.0
            if scale and dark_exptime:
                light_exptime = frame.header.get("EXPTIME")
                if light_exptime:
                    factor = light_exptime / dark_exptime
            return _with_data(
                frame, np.asarray(frame.data, dtype=float) - master * factor
            )

        return _map_lights(data, transform)

    return operator


def flat_fielding(combine: FrameCombiner = median_master) -> Operator:
    """Build a flat-fielding operator.

    For each filter, builds a master flat from that filter's flat frames,
    normalizes it by its own mean (so it encodes only relative response), and
    divides every light of that filter by it. Filters with no flats are left
    unchanged.

    :param combine: how to combine the flat frames into each master flat.
    :returns: an ``ImageData -> ImageData`` calibration operator.
    """

    def operator(data: ImageData) -> ImageData:
        new_lights = dict(data.lights)
        for filt, frames in data.lights.items():
            if not data.flats.get(filt):
                continue
            master = np.asarray(data.master("flats", combine, filt=filt).data, dtype=float)
            normalised = master / master.mean()
            new_lights[filt] = tuple(
                _with_data(frame, np.asarray(frame.data, dtype=float) / normalised)
                for frame in frames
            )
        return data.with_lights(new_lights)

    return operator


def calibrate_coordinator(
    operators: Sequence[Operator], data: ImageData
) -> ImageData:
    """Coordinate Calibrate: apply each calibration operator, then drop the calibration frames.

    Like :func:`~pmo_stacklab.modules.core.process.sequential` but with a final
    :meth:`ImageData.drop_calibration_frames`: calibration *consumes* the
    darks/bias/flats, so the container that leaves this process contains only
    calibrated lights.

    :param operators: the calibration operators to apply, in order (conventionally
        bias -> dark -> flat).
    :param data: the working data, including the calibration frame sets.
    :returns: a new ImageData of calibrated lights with the calibration sets removed.
    """
    for operator in operators:
        data = operator(data)
    return data.drop_calibration_frames()


def build_calibrate(*operators: Operator) -> Process[Operator]:
    """Build the Calibrate :class:`Process` from the chosen calibration operators.

    :param operators: calibration operators in application order, e.g.
        ``build_calibrate(bias_subtraction(), dark_subtraction(), flat_fielding())``.
        Omit any step you do not want applied.
    :returns: a Calibrate process ready to ``run`` on an :class:`ImageData`.
    """
    return Process(
        name="Calibrate",
        operators=tuple(operators),
        coordinator=calibrate_coordinator,
    )
