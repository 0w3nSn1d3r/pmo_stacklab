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

    def test_region_crops_full_res(self) -> None:
        # A small region of a large frame should render at (near) the region's
        # full-resolution pixel size -- i.e. far larger than that region looks in
        # the downsampled full-frame overview.
        data = np.linspace(0, 1000, 2000 * 2000).reshape(2000, 2000)
        # Centre quarter region: x,y in [0.375, 0.625] -> 500x500 full-res pixels.
        png = render_png(_frame(data), region=(0.375, 0.375, 0.625, 0.625))
        w, h = _png_size(png)
        self.assertEqual((w, h), (500, 500))  # full-res, under the 1024 cap

    def test_region_shares_full_frame_levels(self) -> None:
        # The black/white points are fixed on the whole frame, so a crop of a dim
        # corner stays dim (it must NOT be re-normalized to its own local range).
        data = np.zeros((100, 100))
        data[90:, 90:] = 10.0       # one bright corner sets the white point
        # Crop the dark top-left corner; with shared levels it should be near-black.
        png = render_png(_frame(data), stretch="linear", region=(0.0, 0.0, 0.2, 0.2))
        from PIL import Image  # local import; Pillow is a dependency
        arr = np.asarray(Image.open(io.BytesIO(png)))
        self.assertLess(int(arr.max()), 30)  # dark, because levels are global

    def test_large_region_downsampled_to_cap(self) -> None:
        data = np.zeros((4000, 4000))
        png = render_png(_frame(data), region=(0.0, 0.0, 1.0, 1.0), max_side=1024)
        self.assertLessEqual(max(_png_size(png)), 1024)


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

    def test_zoom_params_accepted(self) -> None:
        resp = self.client.get("/api/preview/Upload/R.png?cx=0.5&cy=0.5")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "image/png")

    def test_zoom_requires_both_coords(self) -> None:
        resp = self.client.get("/api/preview/Upload/R.png?cx=0.5")
        self.assertEqual(resp.status_code, 400)

    def test_zoom_coords_out_of_range_400(self) -> None:
        resp = self.client.get("/api/preview/Upload/R.png?cx=1.5&cy=0.5")
        self.assertEqual(resp.status_code, 400)


class ZoomRegionTests(unittest.TestCase):
    def test_centres_and_clamps(self) -> None:
        from pmo_stacklab.app.blueprints.process import _zoom_region, _ZOOM_FRACTION

        self.assertIsNone(_zoom_region(None, None))
        # A central click yields a tile centred on it.
        x0, y0, x1, y1 = _zoom_region("0.5", "0.5")
        self.assertAlmostEqual(x1 - x0, _ZOOM_FRACTION)
        self.assertAlmostEqual((x0 + x1) / 2, 0.5)
        # A corner click clamps the tile fully inside [0, 1].
        x0, y0, x1, y1 = _zoom_region("0.0", "0.0")
        self.assertAlmostEqual(x0, 0.0)
        self.assertAlmostEqual(x1, _ZOOM_FRACTION)

    def test_partial_coords_raise(self) -> None:
        from pmo_stacklab.app.blueprints.process import _zoom_region

        with self.assertRaises(ValueError):
            _zoom_region("0.5", None)


if __name__ == "__main__":
    unittest.main()
