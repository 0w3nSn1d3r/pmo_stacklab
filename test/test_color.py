"""Tests for colour combination (core.color_combine) and the /api/color routes."""
from __future__ import annotations

import io
import unittest

import numpy as np
from astropy.nddata import CCDData

from pmo_stacklab.app.factory import build_app
from pmo_stacklab.app.blueprints.process import COLOR_KEY, UPLOAD_KEY
from pmo_stacklab.modules.core import (
    COLOR_COMBINE,
    ImageData,
    RGBImage,
    combine_image_data,
)
from pmo_stacklab.modules.core.color_combine import build_linear, build_lupton


def _stacked(values: dict[str, float], shape=(8, 8)) -> ImageData:
    """A stacked ImageData: one uniform frame per filter at the given value."""
    frames = [
        CCDData(np.full(shape, v, dtype=float), unit="adu", meta={"FILTER": f})
        for f, v in values.items()
    ]
    return ImageData.from_frames(frames)


class CombineTests(unittest.TestCase):
    def test_linear_maps_channels(self) -> None:
        img = _stacked({"R": 100.0, "G": 50.0, "B": 10.0})
        rgb = combine_image_data(
            img, {"red": "R", "green": "G", "blue": "B"}, build_linear()
        )
        self.assertIsInstance(rgb, RGBImage)
        self.assertEqual(rgb.data.shape, (8, 8, 3))
        self.assertEqual(rgb.data.dtype, np.uint8)
        self.assertEqual(rgb.mapping["red"], "R")

    def test_unmapped_channel_is_black(self) -> None:
        img = _stacked({"R": 100.0})
        rgb = combine_image_data(
            img, {"red": "R", "green": None, "blue": None}, build_linear()
        )
        # Green and blue planes are zero everywhere.
        self.assertEqual(int(rgb.data[..., 1].max()), 0)
        self.assertEqual(int(rgb.data[..., 2].max()), 0)

    def test_lupton_runs(self) -> None:
        img = _stacked({"R": 100.0, "G": 60.0, "B": 30.0})
        rgb = combine_image_data(
            img, {"red": "R", "green": "G", "blue": "B"}, build_lupton(stretch=5.0, Q=8.0)
        )
        self.assertEqual(rgb.data.shape, (8, 8, 3))

    def test_requires_at_least_one_channel(self) -> None:
        img = _stacked({"R": 100.0})
        with self.assertRaises(ValueError):
            combine_image_data(img, {"red": None, "green": None, "blue": None}, build_linear())

    def test_unknown_filter_raises(self) -> None:
        img = _stacked({"R": 100.0})
        with self.assertRaises(ValueError):
            combine_image_data(img, {"red": "Z", "green": None, "blue": None}, build_linear())

    def test_unstacked_filter_raises(self) -> None:
        # Two frames for R -> not stacked; colour combine must refuse.
        frames = [
            CCDData(np.ones((4, 4)), unit="adu", meta={"FILTER": "R"}),
            CCDData(np.ones((4, 4)), unit="adu", meta={"FILTER": "R"}),
        ]
        img = ImageData.from_frames(frames)
        with self.assertRaises(ValueError):
            combine_image_data(img, {"red": "R", "green": None, "blue": None}, build_linear())

    def test_mismatched_shapes_raise(self) -> None:
        frames = [
            CCDData(np.ones((8, 8)), unit="adu", meta={"FILTER": "R"}),
            CCDData(np.ones((4, 4)), unit="adu", meta={"FILTER": "G"}),
        ]
        img = ImageData.from_frames(frames)
        with self.assertRaises(ValueError):
            combine_image_data(img, {"red": "R", "green": "G", "blue": None}, build_linear())


class ColorRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = build_app()
        self.client = self.app.test_client()
        with self.client.session_transaction() as sess:
            sess["session_id"] = "color-session"
        # Seed a stacked image under UPLOAD (the latest-stacked fallback).
        img = _stacked({"R": 100.0, "G": 50.0, "B": 10.0})
        self.app.extensions["pmo_store"].put("color-session", UPLOAD_KEY, img)

    def test_schema_lists_filters_and_default_mapping(self) -> None:
        resp = self.client.get("/api/color")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(set(body["filters"]), {"R", "G", "B"})
        self.assertEqual(body["default_mapping"]["red"], "R")
        self.assertEqual([a["name"] for a in body["combine"]["algorithms"]], ["lupton", "linear"])

    def test_combine_then_fetch_png(self) -> None:
        resp = self.client.post(
            "/api/color",
            json={
                "algorithm": "linear",
                "mapping": {"red": "R", "green": "G", "blue": "B"},
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["mapping"]["red"], "R")
        stored = self.app.extensions["pmo_store"].get("color-session", COLOR_KEY)
        self.assertIsInstance(stored, RGBImage)

        png = self.client.get("/api/color.png")
        self.assertEqual(png.status_code, 200)
        self.assertEqual(png.mimetype, "image/png")
        self.assertEqual(png.get_data()[:8], b"\x89PNG\r\n\x1a\n")

    def test_png_before_combine_404(self) -> None:
        self.assertEqual(self.client.get("/api/color.png").status_code, 404)

    def test_combine_bad_filter_400(self) -> None:
        resp = self.client.post(
            "/api/color", json={"algorithm": "linear", "mapping": {"red": "Z"}}
        )
        self.assertEqual(resp.status_code, 400)

    def test_schema_409_when_nothing_stacked(self) -> None:
        with self.client.session_transaction() as sess:
            sess["session_id"] = "empty-color-session"
        self.assertEqual(self.client.get("/api/color").status_code, 409)

    def _combine(self) -> None:
        self.client.post(
            "/api/color",
            json={"algorithm": "linear", "mapping": {"red": "R", "green": "G", "blue": "B"}},
        )

    def test_download_png(self) -> None:
        self._combine()
        resp = self.client.get("/api/color/download.png")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "image/png")
        self.assertIn("attachment", resp.headers["Content-Disposition"])
        self.assertIn("StackLab_color.png", resp.headers["Content-Disposition"])
        self.assertEqual(resp.get_data()[:8], b"\x89PNG\r\n\x1a\n")

    def test_download_fits_is_three_plane_cube_with_mapping(self) -> None:
        import io as _io
        from astropy.io import fits

        self._combine()
        resp = self.client.get("/api/color/download.fits")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.mimetype, "application/fits")
        self.assertIn("StackLab_color.fits", resp.headers["Content-Disposition"])
        hdul = fits.open(_io.BytesIO(resp.get_data()))
        self.assertEqual(hdul[0].data.shape[0], 3)  # (3, H, W) channel cube
        self.assertEqual(hdul[0].header["CHANR"], "R")  # mapping recorded
        self.assertEqual(hdul[0].header["CHANB"], "B")

    def test_download_before_combine_404(self) -> None:
        self.assertEqual(self.client.get("/api/color/download.png").status_code, 404)

    def test_download_unknown_format_400(self) -> None:
        self._combine()
        self.assertEqual(self.client.get("/api/color/download.tiff").status_code, 400)


if __name__ == "__main__":
    unittest.main()
