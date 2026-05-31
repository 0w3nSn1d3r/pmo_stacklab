"""Tests for preview rendering (core.preview) and the /api/preview routes."""
from __future__ import annotations

import io
import unittest

import numpy as np
from astropy.nddata import CCDData

from pmo_stacklab.app.factory import build_app
from pmo_stacklab.app.blueprints.process import UPLOAD_KEY
from pmo_stacklab.modules.core import ImageData, downsample, render_png


def _frame(data: np.ndarray, *, filt: str = "R") -> CCDData:
    return CCDData(np.asarray(data, dtype=float), unit="adu", meta={"FILTER": filt})


def _png_size(data: bytes) -> tuple[int, int]:
    """Parse a PNG's (width, height) from its IHDR without an image library."""
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    width = int.from_bytes(data[16:20], "big")
    height = int.from_bytes(data[20:24], "big")
    return width, height


class RenderTests(unittest.TestCase):
    def test_downsample_caps_longest_side(self) -> None:
        small = downsample(np.zeros((2000, 3000)), max_side=1000)
        self.assertLessEqual(max(small.shape), 1000)

    def test_downsample_noop_when_small(self) -> None:
        arr = np.zeros((50, 40))
        self.assertEqual(downsample(arr, max_side=1000).shape, (50, 40))

    def test_render_png_returns_valid_png(self) -> None:
        png = render_png(_frame(np.linspace(0, 1000, 64 * 64).reshape(64, 64)))
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(_png_size(png), (64, 64))

    def test_render_png_handles_nan(self) -> None:
        data = np.full((16, 16), 100.0)
        data[0, 0] = np.nan  # e.g. an off-grid pixel from reprojection
        png = render_png(_frame(data))  # must not raise
        self.assertEqual(png[:8], b"\x89PNG\r\n\x1a\n")

    def test_unknown_stretch_rejected(self) -> None:
        with self.assertRaises(ValueError):
            render_png(_frame(np.ones((8, 8))), stretch="bogus")

    def test_stretch_changes_pixels(self) -> None:
        # A smooth gradient of mid-tones should render differently under a weak vs
        # strong asinh boost (a degenerate all-or-nothing image would not, since
        # the percentile clip leaves only 0s and 1s for the stretch to act on).
        data = np.linspace(0, 1000, 64 * 64).reshape(64, 64)
        low = render_png(_frame(data), stretch="asinh", intensity=0.1)
        high = render_png(_frame(data), stretch="asinh", intensity=0.9)
        self.assertNotEqual(low, high)


class PreviewRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = build_app()
        self.client = self.app.test_client()
        with self.client.session_transaction() as sess:
            sess["session_id"] = "preview-session"
        img = ImageData.from_frames(
            [_frame(np.linspace(0, 500, 256).reshape(16, 16), filt="R"),
             _frame(np.linspace(0, 500, 256).reshape(16, 16), filt="G")]
        )
        self.app.extensions["pmo_store"].put("preview-session", UPLOAD_KEY, img)

    def test_lists_filters(self) -> None:
        resp = self.client.get("/api/preview/Upload")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(set(resp.get_json()["filters"]), {"R", "G"})

    def test_serves_png(self) -> None:
        resp = self.client.get("/api/preview/Upload/R.png")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "image/png")
        self.assertEqual(resp.get_data()[:8], b"\x89PNG\r\n\x1a\n")

    def test_png_accepts_display_params(self) -> None:
        resp = self.client.get("/api/preview/Upload/R.png?stretch=log&intensity=0.7")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "image/png")

    def test_unknown_step_404(self) -> None:
        self.assertEqual(self.client.get("/api/preview/Nope").status_code, 404)

    def test_unknown_filter_404(self) -> None:
        self.assertEqual(self.client.get("/api/preview/Upload/Z.png").status_code, 404)

    def test_bad_stretch_400(self) -> None:
        resp = self.client.get("/api/preview/Upload/R.png?stretch=bogus")
        self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main()
