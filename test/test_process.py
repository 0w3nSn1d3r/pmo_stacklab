"""Tests for the generic Process class and the sequential coordinator."""
from __future__ import annotations

import unittest
from collections.abc import Sequence

import numpy as np
from astropy.nddata import CCDData

from pmo_stacklab.modules.core import ImageData, Operator, Process, sequential


def _light(value: float) -> CCDData:
    """Build a small uniform light frame (all pixels == ``value``) under filter 'L'."""
    return CCDData(
        np.full((4, 4), value, dtype=float),
        unit="adu",
        meta={"FILTER": "L", "EXPTIME": 1.0},
    )


def _scale(factor: float) -> Operator:
    """An operator that multiplies every light frame's pixel data by ``factor``."""

    def operator(data: ImageData) -> ImageData:
        scaled = {
            filt: tuple(
                CCDData(frame.data * factor, unit=frame.unit, meta=frame.header)
                for frame in frames
            )
            for filt, frames in data.lights.items()
        }
        return data.with_lights(scaled)

    return operator


class SequentialCoordinatorTests(unittest.TestCase):
    """The :func:`sequential` coordinator applies operators as a left fold."""

    def test_applies_operators_in_order(self) -> None:
        data = ImageData.from_frames([_light(1.0)])
        # x2 then x3 -> x6
        result = sequential((_scale(2.0), _scale(3.0)), data)
        self.assertEqual(float(result.lights["L"][0].data.mean()), 6.0)

    def test_no_operators_is_identity(self) -> None:
        data = ImageData.from_frames([_light(5.0)])
        result = sequential((), data)
        self.assertEqual(float(result.lights["L"][0].data.mean()), 5.0)


class ProcessTests(unittest.TestCase):
    """A Process delegates :meth:`run` to its coordinator over its operators."""

    def test_run_delegates_to_coordinator(self) -> None:
        process: Process[Operator] = Process(
            name="Scale",
            operators=(_scale(2.0), _scale(5.0)),
            coordinator=sequential,
        )
        data = ImageData.from_frames([_light(1.0)])
        result = process.run(data)
        self.assertEqual(process.name, "Scale")
        # x2 then x5 -> x10
        self.assertEqual(float(result.lights["L"][0].data.mean()), 10.0)

    def test_custom_coordinator_overrides_sequencing(self) -> None:
        # A coordinator may ignore the operators entirely; here it is the
        # identity, proving run() defers wholly to the coordinator.
        def identity(operators: Sequence[Operator], data: ImageData) -> ImageData:
            return data

        process: Process[Operator] = Process(
            name="Noop", operators=(_scale(99.0),), coordinator=identity
        )
        data = ImageData.from_frames([_light(7.0)])
        self.assertEqual(float(process.run(data).lights["L"][0].data.mean()), 7.0)


if __name__ == "__main__":
    unittest.main()
