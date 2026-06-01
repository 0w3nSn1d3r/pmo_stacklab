"""Tests for quality metrics (core.metrics) and the /api/metrics route."""
from __future__ import annotations

import unittest

import numpy as np
from astropy.nddata import CCDData

from pmo_stacklab.app.factory import build_app
from pmo_stacklab.app.blueprints.process import UPLOAD_KEY
from pmo_stacklab.modules.core import ImageData, frame_metrics


def _frame(data: np.ndarray, *, filt: str = "R", mask: np.ndarray | None = None) -> CCDData:
    return CCDData(
        np.asarray(data, dtype=float), unit="adu", meta={"FILTER": filt}, mask=mask
    )


class FrameMetricsTests(unittest.TestCase):
    def test_basic_stats(self) -> None:
        data = np.array([[0.0, 2.0], [4.0, 6.0]])
        m = frame_metrics(_frame(data))
        self.assertEqual(m["count"], 4)
        self.assertEqual(m["min"], 0.0)
        self.assertEqual(m["max"], 6.0)
        self.assertEqual(m["mean"], 3.0)
        self.assertEqual(m["median"], 3.0)
        self.assertAlmostEqual(m["std"], float(np.std(data)))

    def test_excludes_masked_pixels(self) -> None:
        data = np.array([[1.0, 1.0], [1.0, 1000.0]])
        mask = np.array([[False, False], [False, True]])  # mask the outlier
        m = frame_metrics(_frame(data, mask=mask))
        self.assertEqual(m["count"], 3)
        self.assertEqual(m["max"], 1.0)  # the 1000 is excluded
        self.assertEqual(m["mean"], 1.0)

    def test_excludes_nan(self) -> None:
        data = np.array([[1.0, np.nan], [3.0, 5.0]])
        m = frame_metrics(_frame(data))
        self.assertEqual(m["count"], 3)
        self.assertEqual(m["mean"], 3.0)  # mean(1,3,5)

    def test_all_invalid_returns_count_zero(self) -> None:
        data = np.full((2, 2), np.nan)
        m = frame_metrics(_frame(data))
        self.assertEqual(m, {"count": 0})

    def test_results_are_plain_floats(self) -> None:
        m = frame_metrics(_frame(np.ones((3, 3))))
        # JSON-safety: every value must be a built-in int/float, not numpy scalar.
        for key, value in m.items():
            self.assertIn(type(value), (int, float), key)


class MetricsRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = build_app()
        self.client = self.app.test_client()
        with self.client.session_transaction() as sess:
            sess["session_id"] = "metrics-session"
        img = ImageData.from_frames(
            [_frame(np.array([[0.0, 10.0], [20.0, 30.0]]), filt="R"),
             _frame(np.full((2, 2), 5.0), filt="G")]
        )
        self.app.extensions["pmo_store"].put("metrics-session", UPLOAD_KEY, img)

    def test_returns_per_filter_metrics(self) -> None:
        resp = self.client.get("/api/metrics/Upload")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(set(body["filters"]), {"R", "G"})
        self.assertEqual(body["filters"]["R"]["max"], 30.0)
        self.assertEqual(body["filters"]["G"]["mean"], 5.0)

    def test_unknown_step_404(self) -> None:
        self.assertEqual(self.client.get("/api/metrics/Nope").status_code, 404)


if __name__ == "__main__":
    unittest.main()
