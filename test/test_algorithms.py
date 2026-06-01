"""Tests for the per-process algorithm registries (Stack and Calibrate).

Verifies that the declared Subprocess registries build *working* operators for
their processes and that their schemas serialize to JSON -- the contract the
generalized endpoint and the frontend depend on.
"""
from __future__ import annotations

import json
import math
import unittest

import numpy as np
from astropy.nddata import CCDData

from pmo_stacklab.modules.core import ImageData
from pmo_stacklab.modules.stacking import COADDITION, OUTLIER_REJECTION, build_stack
from pmo_stacklab.modules.calibration import (
    BIAS_SUBTRACTION,
    DARK_SUBTRACTION,
    FLAT_FIELDING,
    build_calibrate,
)


def _light(filt: str, value: float, *, exptime: float | None = None) -> CCDData:
    meta: dict[str, object] = {"FILTER": filt}
    if exptime is not None:
        meta["EXPTIME"] = exptime
    return CCDData(np.full((3, 3), float(value), dtype=float), unit="adu", meta=meta)


class StackRegistryTests(unittest.TestCase):
    def _run_stack(
        self,
        img: ImageData,
        rejection_name: str,
        coadd_name: str,
        *,
        rejection_params: dict[str, object] | None = None,
        coadd_params: dict[str, object] | None = None,
    ) -> ImageData:
        outlier = OUTLIER_REJECTION.build(rejection_name, rejection_params)
        coadd = COADDITION.build(coadd_name, coadd_params)
        return build_stack(outlier, coadd).run(img)

    def test_median_and_mean_coaddition(self) -> None:
        img = ImageData.from_frames(
            [_light("R", 1.0), _light("R", 3.0), _light("R", 11.0)]
        )
        median = self._run_stack(img, "none", "median")
        self.assertEqual(float(median.lights["R"][0].data.mean()), 3.0)  # median(1,3,11)
        mean = self._run_stack(img, "none", "mean")
        self.assertEqual(float(mean.lights["R"][0].data.mean()), 5.0)  # mean(1,3,11)

    def test_biweight_param_wired(self) -> None:
        img = ImageData.from_frames(
            [_light("R", 7.0), _light("R", 7.0), _light("R", 7.0)]
        )
        out = self._run_stack(img, "none", "biweight", coadd_params={"c": 6.0})
        # The biweight location of identical values is that value.
        self.assertAlmostEqual(float(out.lights["R"][0].data.mean()), 7.0)

    def test_sigma_clip_rejects_outlier(self) -> None:
        frames = [_light("R", v) for v in (8.0, 10.0, 12.0, 9.0, 11.0, 1000.0)]
        img = ImageData.from_frames(frames)
        out = self._run_stack(img, "sigma_clip", "mean", rejection_params={"sigma": 3.0})
        value = float(out.lights["R"][0].data.mean())
        # Unclipped mean would be ~175; clipping the 1000 pulls it back near 10.
        self.assertLess(value, 50.0)
        self.assertGreater(value, 5.0)

    def test_winsorize_adapter_runs(self) -> None:
        img = ImageData.from_frames(
            [_light("R", 2.0), _light("R", 4.0), _light("R", 6.0)]
        )
        out = self._run_stack(
            img, "winsorize", "mean", rejection_params={"lower": 0.1, "upper": 0.1}
        )
        value = float(out.lights["R"][0].data.mean())
        self.assertTrue(math.isfinite(value))
        self.assertGreaterEqual(value, 2.0)
        self.assertLessEqual(value, 6.0)

    def test_percentile_clip_rejects_outlier(self) -> None:
        # An extreme frame sits above the upper percentile and is masked out before
        # the mean, so the result tracks the inlying frames, not the outlier.
        frames = [_light("R", v) for v in (10.0, 11.0, 9.0, 10.5, 9.5, 5000.0)]
        img = ImageData.from_frames(frames)
        out = self._run_stack(
            img, "percentile_clip", "mean",
            rejection_params={"lower": 5.0, "upper": 95.0},
        )
        value = float(out.lights["R"][0].data.mean())
        self.assertLess(value, 100.0)  # the 5000 outlier was clipped
        self.assertGreater(value, 5.0)

    def test_invalid_param_rejected(self) -> None:
        with self.assertRaises(ValueError):
            OUTLIER_REJECTION.build("sigma_clip", {"sigma": -1.0})

    def test_schema_serializes(self) -> None:
        for subprocess in (OUTLIER_REJECTION, COADDITION):
            json.dumps(subprocess.to_dict())
        names = [a["name"] for a in OUTLIER_REJECTION.to_dict()["algorithms"]]
        self.assertEqual(names, ["none", "sigma_clip", "winsorize", "percentile_clip"])


class CalibrateRegistryTests(unittest.TestCase):
    def test_full_calibration_through_registry(self) -> None:
        img = ImageData.from_frames(
            lights=[_light("R", 100.0, exptime=200)],
            bias=[_light("R", 10.0)],
            darks=[_light("R", 5.0, exptime=100)],
            flats=[_light("R", 4.0)],
        )
        process = build_calibrate(
            BIAS_SUBTRACTION.build("subtract"),
            DARK_SUBTRACTION.build("subtract", {"scale": True}),
            FLAT_FIELDING.build("divide"),
        )
        out = process.run(img)
        # 100 -bias(10)=90 -dark(5)*2=10 ->80 /flat(uniform)=80
        self.assertEqual(float(out.lights["R"][0].data.mean()), 80.0)

    def test_dark_scale_param_wired(self) -> None:
        img = ImageData.from_frames(
            lights=[_light("R", 100.0, exptime=300)],
            darks=[_light("R", 5.0, exptime=100)],
        )
        scaled = build_calibrate(DARK_SUBTRACTION.build("subtract", {"scale": True})).run(img)
        self.assertEqual(float(scaled.lights["R"][0].data.mean()), 85.0)  # 100 - 5*3
        unscaled = build_calibrate(DARK_SUBTRACTION.build("subtract", {"scale": False})).run(img)
        self.assertEqual(float(unscaled.lights["R"][0].data.mean()), 95.0)  # 100 - 5

    def test_schema_serializes_with_bool_param(self) -> None:
        schema = DARK_SUBTRACTION.to_dict()
        json.dumps(schema)
        param = schema["algorithms"][0]["parameters"][0]
        self.assertEqual(param["type"], "bool")
        self.assertEqual(param["name"], "scale")


if __name__ == "__main__":
    unittest.main()
