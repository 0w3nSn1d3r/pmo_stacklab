"""Tests for the Calibrate process: per-step calibration and frame consumption."""
from __future__ import annotations

import unittest

import numpy as np
from astropy.nddata import CCDData
from astropy.wcs import WCS

from pmo_stacklab.modules.core import ImageData
from pmo_stacklab.modules.calibration import (
    bias_subtraction,
    build_calibrate,
    dark_subtraction,
    flat_fielding,
)


def _frame(
    value: float | np.ndarray,
    *,
    filt: str = "R",
    exptime: float | None = None,
    shape: tuple[int, int] = (2, 2),
) -> CCDData:
    """A uniform (or explicit-array) calibration/light frame under filter ``filt``."""
    meta: dict[str, object] = {"FILTER": filt}
    if exptime is not None:
        meta["EXPTIME"] = exptime
    data = value if isinstance(value, np.ndarray) else np.full(shape, float(value))
    return CCDData(np.asarray(data, dtype=float), unit="adu", meta=meta)


class CalibrateProcessTests(unittest.TestCase):
    def test_full_calibration(self) -> None:
        # light 100 -> -bias(10)=90 -> -dark(5)*scale(200/100=2)=10 -> 80 -> /flat(uniform)=80
        img = ImageData.from_frames(
            lights=[_frame(100, exptime=200)],
            bias=[_frame(10, exptime=0), _frame(10, exptime=0)],
            darks=[_frame(5, exptime=100), _frame(5, exptime=100)],
            flats=[_frame(4, filt="R"), _frame(4, filt="R")],
        )
        process = build_calibrate(
            bias_subtraction(), dark_subtraction(), flat_fielding()
        )
        out = process.run(img)
        self.assertEqual(process.name, "Calibrate")
        self.assertEqual(float(out.lights["R"][0].data.mean()), 80.0)

    def test_consumes_calibration_frames(self) -> None:
        img = ImageData.from_frames(
            lights=[_frame(100, exptime=10)],
            bias=[_frame(10)],
            darks=[_frame(5, exptime=10)],
            flats=[_frame(4)],
        )
        out = build_calibrate(
            bias_subtraction(), dark_subtraction(), flat_fielding()
        ).run(img)
        self.assertEqual(out.darks, ())
        self.assertEqual(out.bias, ())
        self.assertEqual(out.flats, {})

    def test_dark_scaling_by_exposure(self) -> None:
        # dark 5 @ 100s; light @ 300s -> factor 3 -> subtract 15
        img = ImageData.from_frames(
            lights=[_frame(100, exptime=300)],
            darks=[_frame(5, exptime=100)],
        )
        scaled = build_calibrate(dark_subtraction(scale=True)).run(img)
        self.assertEqual(float(scaled.lights["R"][0].data.mean()), 85.0)  # 100 - 15
        unscaled = build_calibrate(dark_subtraction(scale=False)).run(img)
        self.assertEqual(float(unscaled.lights["R"][0].data.mean()), 95.0)  # 100 - 5

    def test_flat_fielding_divides_by_normalised_flat(self) -> None:
        flat = np.array([[2.0, 2.0], [6.0, 6.0]])  # mean 4 -> normalised [[.5,.5],[1.5,1.5]]
        light = np.full((2, 2), 6.0)
        img = ImageData.from_frames(
            lights=[_frame(light, filt="R")],
            flats=[_frame(flat, filt="R")],
        )
        out = build_calibrate(flat_fielding()).run(img)
        result = np.asarray(out.lights["R"][0].data)
        np.testing.assert_allclose(result, [[12.0, 12.0], [4.0, 4.0]])

    def test_missing_frames_are_noops(self) -> None:
        img = ImageData.from_frames(lights=[_frame(100)])  # no calibration frames
        out = build_calibrate(
            bias_subtraction(), dark_subtraction(), flat_fielding()
        ).run(img)
        self.assertEqual(float(out.lights["R"][0].data.mean()), 100.0)

    def test_preserves_wcs(self) -> None:
        w = WCS(naxis=2)
        w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
        w.wcs.crpix = [1, 1]; w.wcs.crval = [10, 20]; w.wcs.cdelt = [-1e-3, 1e-3]
        light = CCDData(
            np.full((2, 2), 100.0), unit="adu", wcs=w, meta={"FILTER": "R", "EXPTIME": 10}
        )
        img = ImageData.from_frames(lights=[light], bias=[_frame(10)])
        out = build_calibrate(bias_subtraction()).run(img)
        self.assertIsNotNone(out.lights["R"][0].wcs)


if __name__ == "__main__":
    unittest.main()
