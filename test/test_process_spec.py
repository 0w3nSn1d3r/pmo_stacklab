"""Tests for ProcessSpec: building a runnable Process from submitted choices."""
from __future__ import annotations

import json
import unittest

import numpy as np
from astropy.nddata import CCDData

from pmo_stacklab.modules.core import (
    Algorithm,
    ImageData,
    Operator,
    ProcessSpec,
    Subprocess,
    sequential,
)
from pmo_stacklab.modules.calibration import CALIBRATE
from pmo_stacklab.modules.stacking import STACK


def _light(value: float, *, filt: str = "R", exptime: float | None = None) -> CCDData:
    meta: dict[str, object] = {"FILTER": filt}
    if exptime is not None:
        meta["EXPTIME"] = exptime
    return CCDData(np.full((2, 2), float(value), dtype=float), unit="adu", meta=meta)


def _scale(factor: float) -> Operator:
    def operator(data: ImageData) -> ImageData:
        return data.with_lights(
            {
                filt: tuple(
                    CCDData(frame.data * factor, unit=frame.unit, meta=frame.header)
                    for frame in frames
                )
                for filt, frames in data.lights.items()
            }
        )

    return operator


class ProcessSpecBuildTests(unittest.TestCase):
    @staticmethod
    def _spec() -> ProcessSpec[Operator]:
        return ProcessSpec(
            name="T",
            subprocesses=(
                Subprocess(
                    name="a", algorithms=(Algorithm(name="x2", builder=lambda: _scale(2.0)),)
                ),
                Subprocess(
                    name="b", algorithms=(Algorithm(name="x3", builder=lambda: _scale(3.0)),)
                ),
            ),
            coordinator=sequential,
        )

    def test_builds_process_in_subprocess_order(self) -> None:
        proc = self._spec().build({"a": {"algorithm": "x2"}, "b": {"algorithm": "x3"}})
        self.assertEqual(proc.name, "T")
        out = proc.run(ImageData.from_frames([_light(1.0)]))
        self.assertEqual(float(out.lights["R"][0].data.mean()), 6.0)  # x2 then x3

    def test_missing_config_uses_first_algorithm(self) -> None:
        # Empty configs -> each subprocess uses its first algorithm with defaults.
        out = self._spec().build().run(ImageData.from_frames([_light(1.0)]))
        self.assertEqual(float(out.lights["R"][0].data.mean()), 6.0)

    def test_unknown_algorithm_raises(self) -> None:
        with self.assertRaises(KeyError):
            self._spec().build({"a": {"algorithm": "nope"}})

    def test_to_dict_serializes_full_process(self) -> None:
        schema = self._spec().to_dict()
        self.assertEqual(schema["name"], "T")
        self.assertEqual([s["name"] for s in schema["subprocesses"]], ["a", "b"])
        json.dumps(schema)


class RegisteredProcessSpecTests(unittest.TestCase):
    def test_stack_spec_builds_and_runs(self) -> None:
        img = ImageData.from_frames([_light(1.0), _light(3.0), _light(11.0)])
        proc = STACK.build(
            {
                "outlier_rejection": {"algorithm": "none"},
                "coaddition": {"algorithm": "median"},
            }
        )
        out = proc.run(img)
        self.assertEqual(proc.name, "Stack")
        self.assertTrue(out.is_stacked)
        self.assertEqual(float(out.lights["R"][0].data.mean()), 3.0)  # median(1,3,11)

    def test_stack_spec_defaults_are_runnable(self) -> None:
        img = ImageData.from_frames([_light(2.0), _light(4.0)])
        out = STACK.build().run(img)  # defaults: none + median
        self.assertTrue(out.is_stacked)

    def test_calibrate_spec_builds_and_runs(self) -> None:
        img = ImageData.from_frames(
            lights=[_light(100.0, exptime=200)],
            bias=[_light(10.0)],
            darks=[_light(5.0, exptime=100)],
            flats=[_light(4.0)],
        )
        proc = CALIBRATE.build(
            {
                "bias_subtraction": {"algorithm": "subtract"},
                "dark_subtraction": {"algorithm": "subtract", "params": {"scale": True}},
                "flat_fielding": {"algorithm": "divide"},
            }
        )
        out = proc.run(img)
        self.assertEqual(proc.name, "Calibrate")
        self.assertEqual(float(out.lights["R"][0].data.mean()), 80.0)

    def test_specs_serialize_to_json(self) -> None:
        for spec in (STACK, CALIBRATE):
            json.dumps(spec.to_dict())
        self.assertEqual(
            [s["name"] for s in STACK.to_dict()["subprocesses"]],
            ["outlier_rejection", "coaddition"],
        )


if __name__ == "__main__":
    unittest.main()
