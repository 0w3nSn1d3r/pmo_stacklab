"""Tests for the FITS loader and the /api/upload endpoint.

FITS frames are generated in memory (no fixture files on disk) and posted as
multipart uploads, exercising the real read path end-to-end.
"""
from __future__ import annotations

import io
import unittest

import numpy as np
from astropy.io import fits
from astropy.wcs import WCS

from pmo_stacklab.app.factory import build_app
from pmo_stacklab.app.blueprints.process import UPLOAD_KEY
from pmo_stacklab.modules.core import load_frame, load_image_data


def _fits_bytes(
    value: float,
    *,
    filt: str | None = None,
    exptime: float | None = None,
    with_wcs: bool = True,
    bunit: str | None = None,
) -> io.BytesIO:
    """Build a single-frame FITS file in memory and return it as a seekable buffer."""
    if with_wcs:
        w = WCS(naxis=2)
        w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
        w.wcs.crpix = [2, 2]; w.wcs.crval = [10, 20]; w.wcs.cdelt = [-1e-3, 1e-3]
        header = w.to_header()
    else:
        header = fits.Header()
    if filt is not None:
        header["FILTER"] = filt
    if exptime is not None:
        header["EXPTIME"] = exptime
    if bunit is not None:
        header["BUNIT"] = bunit
    buf = io.BytesIO()
    fits.PrimaryHDU(np.full((4, 4), float(value), dtype=np.float32), header).writeto(buf)
    buf.seek(0)
    return buf


class LoaderTests(unittest.TestCase):
    def test_load_frame_parses_wcs_and_strips_keywords(self) -> None:
        frame = load_frame(_fits_bytes(1.0, filt="R"))
        self.assertIsNotNone(frame.wcs)
        self.assertNotIn("CRVAL1", frame.header)  # WCS keys stripped from meta
        self.assertEqual(frame.header["FILTER"], "R")

    def test_load_frame_infers_unit_from_bunit(self) -> None:
        frame = load_frame(_fits_bytes(1.0, bunit="adu"))
        self.assertEqual(str(frame.unit), "adu")

    def test_load_frame_rejects_non_fits(self) -> None:
        with self.assertRaises(ValueError):
            load_frame(io.BytesIO(b"not a fits file"))

    def test_load_image_data_groups_by_filter(self) -> None:
        img = load_image_data(
            lights=[_fits_bytes(1.0, filt="R"), _fits_bytes(2.0, filt="G")],
            darks=[_fits_bytes(0.1)],
        )
        self.assertEqual(set(img.filters), {"R", "G"})
        self.assertEqual(len(img.darks), 1)

    def test_load_image_data_requires_lights(self) -> None:
        with self.assertRaises(ValueError):
            load_image_data(lights=[])


class UploadEndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = build_app()
        self.client = self.app.test_client()

    def _sid(self) -> str:
        with self.client.session_transaction() as sess:
            return sess.get("session_id", "")

    def test_upload_seeds_store_and_reports_counts(self) -> None:
        data = {
            "lights": [
                (_fits_bytes(100.0, filt="R", exptime=200), "l1.fits"),
                (_fits_bytes(120.0, filt="R", exptime=200), "l2.fits"),
            ],
            "darks": [(_fits_bytes(5.0, exptime=100), "d1.fits")],
            "bias": [(_fits_bytes(10.0), "b1.fits")],
            "flats": [(_fits_bytes(4.0, filt="R"), "f1.fits")],
        }
        resp = self.client.post(
            "/api/upload", data=data, content_type="multipart/form-data"
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(body["process"], "Upload")
        self.assertEqual(body["filters"]["R"]["frames"], 2)
        self.assertEqual(body["calibration"]["darks"], 1)
        self.assertEqual(body["calibration"]["bias"], 1)
        self.assertEqual(body["calibration"]["flats"]["R"], 1)

        stored = self.app.extensions["pmo_store"].get(self._sid(), UPLOAD_KEY)
        self.assertIsNotNone(stored)
        self.assertEqual(len(stored.lights["R"]), 2)

    def test_upload_without_lights_returns_400(self) -> None:
        resp = self.client.post(
            "/api/upload",
            data={"darks": [(_fits_bytes(5.0), "d.fits")]},
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 400)

    def test_upload_bad_fits_returns_400(self) -> None:
        resp = self.client.post(
            "/api/upload",
            data={"lights": [(io.BytesIO(b"garbage"), "x.fits")]},
            content_type="multipart/form-data",
        )
        self.assertEqual(resp.status_code, 400)

    def test_upload_then_run_full_pipeline(self) -> None:
        # Upload real frames, then drive Calibrate -> Stack through /api/run.
        data = {
            "lights": [
                (_fits_bytes(100.0, filt="R", exptime=100), "l1.fits"),
                (_fits_bytes(104.0, filt="R", exptime=100), "l2.fits"),
            ],
            "bias": [(_fits_bytes(10.0), "b1.fits")],
        }
        self.assertEqual(
            self.client.post("/api/upload", data=data, content_type="multipart/form-data").status_code,
            200,
        )
        self.assertEqual(
            self.client.post("/api/run", json={"process": "Calibrate", "configs": {}}).status_code,
            200,
        )
        resp = self.client.post(
            "/api/run",
            json={
                "process": "Stack",
                "configs": {
                    "outlier_rejection": {"algorithm": "none"},
                    "coaddition": {"algorithm": "mean"},
                },
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["stacked"])
        out = self.app.extensions["pmo_store"].get(self._sid(), "Stack")
        # lights (100,104) - bias 10 = (90,94); mean = 92.
        self.assertEqual(float(out.lights["R"][0].data.mean()), 92.0)


if __name__ == "__main__":
    unittest.main()
