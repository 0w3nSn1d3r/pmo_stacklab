"""Tests for the Pipeline / PipelineSpec (the whole-pipeline runner)."""
from __future__ import annotations

import unittest

import numpy as np
from astropy.nddata import CCDData

from pmo_stacklab.modules.core import ImageData, Pipeline, PipelineSpec
from pmo_stacklab.modules.calibration import CALIBRATE
from pmo_stacklab.modules.reprojection import REPROJECT
from pmo_stacklab.modules.stacking import STACK


def _light(value: float, *, filt: str = "R", exptime: float | None = None) -> CCDData:
    meta: dict[str, object] = {"FILTER": filt}
    if exptime is not None:
        meta["EXPTIME"] = exptime
    return CCDData(np.full((4, 4), float(value), dtype=float), unit="adu", meta=meta)


_STARS = [(15, 20), (40, 50), (30, 12), (50, 25), (22, 45), (10, 55), (45, 38),
          (18, 33), (35, 28), (52, 48), (28, 58), (48, 14), (12, 40), (38, 8)]


def _star_light(shift: tuple[int, int] = (0, 0), filt: str = "R") -> CCDData:
    """A light frame with enough stars for star-matching registration to solve."""
    img = np.full((64, 64), 10.0)
    for row, col in _STARS:
        r, c = row + shift[0], col + shift[1]
        if 2 <= r < 62 and 2 <= c < 62:
            img[r, c] += 1000
            img[r + 1, c] += 400
            img[r - 1, c] += 400
            img[r, c + 1] += 400
            img[r, c - 1] += 400
    return CCDData(img, unit="adu", meta={"FILTER": filt})


# The real Calibrate -> Reproject -> Stack pipeline, as configured in app ORDER.
SPEC = PipelineSpec(processes=(CALIBRATE, REPROJECT, STACK))


class PipelineRunTests(unittest.TestCase):
    def test_runs_all_processes_in_order(self) -> None:
        # No calibration frames -> Calibrate no-ops; identity Reproject; Stack means.
        img = ImageData.from_frames([_light(2.0), _light(4.0), _light(6.0)])
        recipe = {
            "Calibrate": {},
            "Reproject": {
                "registration": {"algorithm": "none"},
                "alignment": {"algorithm": "nearest"},
            },
            "Stack": {
                "outlier_rejection": {"algorithm": "none"},
                "coaddition": {"algorithm": "mean"},
            },
        }
        out = SPEC.build(recipe).run(img)
        self.assertTrue(out.is_stacked)
        self.assertEqual(float(out.lights["R"][0].data.mean()), 4.0)  # mean(2,4,6)

    def test_full_calibration_through_pipeline(self) -> None:
        img = ImageData.from_frames(
            lights=[_light(100.0, exptime=200), _light(104.0, exptime=200)],
            bias=[_light(10.0)],
            darks=[_light(5.0, exptime=100)],
        )
        recipe = {
            "Reproject": {"registration": {"algorithm": "none"}, "alignment": {"algorithm": "nearest"}},
            "Stack": {"outlier_rejection": {"algorithm": "none"}, "coaddition": {"algorithm": "mean"}},
        }
        out = SPEC.build(recipe).run(img)
        # each light: -bias 10 -dark(5*2=10) -> 80, 84 ; mean = 82.
        self.assertEqual(float(out.lights["R"][0].data.mean()), 82.0)

    def test_empty_recipe_uses_defaults(self) -> None:
        # Every process built from its declared defaults must still run. The
        # default registration is star matching, so this needs a frame with stars
        # in it -- a flat field would give astroalign nothing to match.
        img = ImageData.from_frames([_star_light(), _star_light(shift=(2, -1))])
        out = SPEC.build().run(img)
        self.assertTrue(out.is_stacked)

    def test_returns_pipeline_of_processes(self) -> None:
        pipeline = SPEC.build()
        self.assertIsInstance(pipeline, Pipeline)
        self.assertEqual([p.name for p in pipeline.processes], ["Calibrate", "Reproject", "Stack"])

    def test_invalid_algorithm_raises(self) -> None:
        with self.assertRaises(KeyError):
            SPEC.build({"Stack": {"coaddition": {"algorithm": "nope"}}})


class DefaultRecipeTests(unittest.TestCase):
    def test_default_recipe_shape(self) -> None:
        recipe = SPEC.default_recipe()
        self.assertEqual(set(recipe), {"Calibrate", "Reproject", "Stack"})
        # Each subprocess maps to {algorithm, params} of its first algorithm.
        stack = recipe["Stack"]
        self.assertIn("outlier_rejection", stack)
        self.assertIn("algorithm", stack["coaddition"])
        self.assertIn("params", stack["coaddition"])

    def test_default_recipe_is_runnable(self) -> None:
        img = ImageData.from_frames([_light(1.0), _light(9.0)])
        out = SPEC.build(SPEC.default_recipe()).run(img)
        self.assertTrue(out.is_stacked)

    def test_to_dict_serializes_all_processes(self) -> None:
        import json

        schema = SPEC.to_dict()
        names = [p["name"] for p in schema["processes"]]
        self.assertEqual(names, ["Calibrate", "Reproject", "Stack"])
        json.dumps(schema)


if __name__ == "__main__":
    unittest.main()
