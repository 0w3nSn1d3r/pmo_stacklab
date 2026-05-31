"""Tests for the Post-Process process: background, intensity-scaling, stretch."""
from __future__ import annotations

import json
import unittest

import numpy as np
from astropy.nddata import CCDData
from astropy.wcs import WCS

from pmo_stacklab.modules.core import ImageData
from pmo_stacklab.modules.post_processing import (
    BACKGROUND,
    INTENSITY_SCALING,
    POST_PROCESS,
    STRETCH,
    build_post_process,
)
from pmo_stacklab.modules.post_processing import (
    background_modeling,
    intensity_scaling,
    stretch,
)


def _frame(data: np.ndarray, *, filt: str = "R", wcs=None) -> CCDData:
    return CCDData(np.asarray(data, dtype=float), unit="adu", meta={"FILTER": filt}, wcs=wcs)


def _img(data: np.ndarray) -> ImageData:
    return ImageData.from_frames([_frame(data)])


def _single(out: ImageData) -> np.ndarray:
    return np.asarray(out.lights["R"][0].data, dtype=float)


class BackgroundTests(unittest.TestCase):
    def test_global_removes_pedestal(self) -> None:
        data = np.full((8, 8), 100.0)
        data[4, 4] = 600.0
        out = _single(background_modeling.build_global()(_img(data)))
        # Median (~100) subtracted: background pixels near 0, the star still bright.
        self.assertAlmostEqual(float(np.median(out)), 0.0, places=6)
        self.assertGreater(out.max(), 400)

    def test_sep_2d_flattens_gradient(self) -> None:
        rng = np.random.default_rng(0)
        base = rng.normal(100, 2, (64, 64))
        gradient = np.linspace(0, 80, 64)[None, :]
        out = _single(background_modeling.build_sep_2d(box_size=16)(_img(base + gradient)))
        # The left-to-right gradient should be largely removed: column means flat.
        col_means = out.mean(axis=0)
        self.assertLess(col_means.max() - col_means.min(), 20.0)

    def test_none_is_identity(self) -> None:
        data = np.arange(16.0).reshape(4, 4)
        np.testing.assert_array_equal(
            _single(background_modeling.build_none()(_img(data))), data
        )


class IntensityScalingTests(unittest.TestCase):
    def test_minmax_normalizes_to_unit_range(self) -> None:
        data = np.linspace(50, 1050, 64).reshape(8, 8)
        out = _single(intensity_scaling.build_minmax()(_img(data)))
        self.assertAlmostEqual(float(out.min()), 0.0, places=6)
        self.assertAlmostEqual(float(out.max()), 1.0, places=6)

    def test_percentile_clips_outliers(self) -> None:
        data = np.full((8, 8), 100.0)
        data[0, 0] = 1e6  # one hot pixel
        out = _single(intensity_scaling.build_percentile(99.0)(_img(data)))
        self.assertLessEqual(float(out.max()), 1.0)
        self.assertGreaterEqual(float(out.min()), 0.0)


class StretchTests(unittest.TestCase):
    def test_asinh_boosts_faint_signal(self) -> None:
        # A faint value at 0.1 should be lifted above its linear position.
        data = np.array([[0.0, 0.1], [0.5, 1.0]])
        out = _single(stretch.build_asinh(a=0.1)(_img(data)))
        self.assertGreater(out[0, 1], 0.1)  # 0.1 input mapped higher
        self.assertAlmostEqual(float(out.min()), 0.0, places=6)
        self.assertAlmostEqual(float(out.max()), 1.0, places=6)

    def test_linear_is_identity_on_unit_range(self) -> None:
        data = np.array([[0.0, 0.25], [0.75, 1.0]])
        out = _single(stretch.build_linear()(_img(data)))
        np.testing.assert_allclose(out, data)

    def test_stretch_clips_out_of_range_input(self) -> None:
        data = np.array([[-0.5, 0.5], [1.5, 2.0]])
        out = _single(stretch.build_sqrt()(_img(data)))
        self.assertGreaterEqual(float(out.min()), 0.0)
        self.assertLessEqual(float(out.max()), 1.0)


class PostProcessProcessTests(unittest.TestCase):
    def test_full_chain_runs_and_reveals_faint_signal(self) -> None:
        # Bright star + faint nebulosity on a pedestal; the pipeline should bring
        # the faint signal up into a visible range.
        data = np.full((32, 32), 100.0)
        data[16, 16] = 5000.0      # bright star
        data[8:12, 8:12] += 5.0    # faint nebulosity, just above background
        proc = build_post_process(
            background_modeling.build_global(),
            intensity_scaling.build_percentile(99.5),
            stretch.build_asinh(a=0.05),
        )
        out = _single(proc.run(_img(data)))
        self.assertGreaterEqual(float(out.min()), 0.0)
        self.assertLessEqual(float(out.max()), 1.0)
        # The faint patch should sit clearly above true background after stretch.
        self.assertGreater(out[9, 9], out[0, 0])

    def test_preserves_wcs(self) -> None:
        w = WCS(naxis=2)
        w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
        w.wcs.crpix = [1, 1]; w.wcs.crval = [10, 20]; w.wcs.cdelt = [-1e-3, 1e-3]
        img = ImageData.from_frames([_frame(np.ones((4, 4)), wcs=w)])
        out = build_post_process(stretch.build_linear()).run(img)
        self.assertIsNotNone(out.lights["R"][0].wcs)


class PostProcessSpecTests(unittest.TestCase):
    def test_spec_shape(self) -> None:
        self.assertEqual(POST_PROCESS.name, "Post-Process")
        self.assertEqual(
            [s.name for s in POST_PROCESS.subprocesses],
            ["background", "intensity_scaling", "stretch"],
        )

    def test_spec_builds_and_runs(self) -> None:
        proc = POST_PROCESS.build(
            {
                "background": {"algorithm": "global"},
                "intensity_scaling": {"algorithm": "minmax"},
                "stretch": {"algorithm": "asinh", "params": {"a": 0.1}},
            }
        )
        out = _single(proc.run(_img(np.linspace(0, 1000, 256).reshape(16, 16))))
        self.assertGreaterEqual(float(out.min()), 0.0)
        self.assertLessEqual(float(out.max()), 1.0)

    def test_spec_defaults_runnable(self) -> None:
        out = POST_PROCESS.build().run(_img(np.linspace(0, 100, 64).reshape(8, 8)))
        self.assertEqual(set(out.filters), {"R"})

    def test_schema_serializes(self) -> None:
        for sub in (BACKGROUND, INTENSITY_SCALING, STRETCH):
            json.dumps(sub.to_dict())


if __name__ == "__main__":
    unittest.main()
