"""Tests for graceful, JSON, actionable error handling across the API.

These verify that malformed input and missing endpoints yield clean JSON errors
(never an HTML 500 page), with actionable messages where the fault is the user's.
"""
from __future__ import annotations

import io
import unittest

import numpy as np
from astropy.io import fits

from pmo_stacklab.app.factory import build_app


def _fits(value: float, filt: str = "R") -> io.BytesIO:
    data = np.full((8, 8), float(value), dtype=np.float32)
    h = fits.PrimaryHDU(data)
    h.header["FILTER"] = filt
    h.header["EXPTIME"] = 100.0
    buf = io.BytesIO()
    h.writeto(buf)
    buf.seek(0)
    return buf


class JsonErrorHandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = build_app()
        self.client = self.app.test_client()

    def test_unknown_api_route_returns_json_404(self) -> None:
        resp = self.client.get("/api/does-not-exist")
        self.assertEqual(resp.status_code, 404)
        self.assertEqual(resp.content_type.split(";")[0], "application/json")
        self.assertIn("error", resp.get_json())

    def test_unknown_page_route_stays_html(self) -> None:
        # Non-API routes keep Flask's default (HTML) 404.
        resp = self.client.get("/no-such-page")
        self.assertEqual(resp.status_code, 404)
        self.assertNotEqual(resp.content_type.split(";")[0], "application/json")


class MalformedInputTests(unittest.TestCase):
    """Malformed JSON bodies get a clean, actionable 400 -- never a 500."""

    def setUp(self) -> None:
        self.app = build_app()
        self.client = self.app.test_client()
        with self.client.session_transaction() as sess:
            sess["session_id"] = "err"
        # Seed an upload so /run reaches the build/validation step.
        self.client.post(
            "/api/upload",
            data={"lights": [(_fits(100.0), "l.fits")]},
            content_type="multipart/form-data",
        )

    def _assert_json_4xx(self, resp) -> None:
        self.assertEqual(resp.content_type.split(";")[0], "application/json")
        self.assertGreaterEqual(resp.status_code, 400)
        self.assertLess(resp.status_code, 500)
        self.assertIn("error", resp.get_json())

    def test_run_configs_not_a_dict(self) -> None:
        self._assert_json_4xx(
            self.client.post("/api/run", json={"process": "Calibrate", "configs": "oops"})
        )

    def test_run_subprocess_config_not_a_dict(self) -> None:
        resp = self.client.post(
            "/api/run",
            json={"process": "Calibrate", "configs": {"bias_subtraction": "x"}},
        )
        self._assert_json_4xx(resp)
        self.assertIn("bias_subtraction", resp.get_json()["error"])

    def test_quickstack_recipe_not_a_dict(self) -> None:
        self._assert_json_4xx(self.client.put("/api/quickstack", json=[1, 2, 3]))

    def test_color_mapping_not_a_dict(self) -> None:
        # Drive a stacked image first so /color reaches validation.
        self.client.post("/api/run", json={"process": "Calibrate", "configs": {}})
        self.client.post(
            "/api/run",
            json={"process": "Reproject", "configs": {"registration": {"algorithm": "none"}, "alignment": {"algorithm": "nearest"}}},
        )
        self.client.post(
            "/api/run",
            json={"process": "Stack", "configs": {"coaddition": {"algorithm": "mean"}}},
        )
        resp = self.client.post("/api/color", json={"algorithm": "linear", "mapping": ["R"]})
        self._assert_json_4xx(resp)


if __name__ == "__main__":
    unittest.main()
