"""Tests for the generalized process API (/api/run and /api/schema).

Upload is a later unit, so the initial ImageData is seeded directly into the store
under a fixed session id (via Flask's session_transaction) -- this exercises the
endpoint's build/run/persist/chaining logic without file handling.
"""
from __future__ import annotations

import unittest

import numpy as np
from astropy.nddata import CCDData

from pmo_stacklab.app.factory import build_app
from pmo_stacklab.app.blueprints.process import UPLOAD_KEY
from pmo_stacklab.modules.core import ImageData


def _light(value: float, *, filt: str = "R", exptime: float | None = None) -> CCDData:
    meta: dict[str, object] = {"FILTER": filt}
    if exptime is not None:
        meta["EXPTIME"] = exptime
    return CCDData(np.full((2, 2), float(value), dtype=float), unit="adu", meta=meta)


class EndpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = build_app()
        self.client = self.app.test_client()
        self.sid = "test-session"

    def _seed_upload(self, img: ImageData) -> None:
        with self.client.session_transaction() as sess:
            sess["session_id"] = self.sid
        self.app.extensions["pmo_store"].put(self.sid, UPLOAD_KEY, img)

    # -- schema routes ----------------------------------------------------

    def test_list_pipeline(self) -> None:
        resp = self.client.get("/api/schema")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["order"], ["Calibrate", "Stack"])

    def test_process_schema(self) -> None:
        resp = self.client.get("/api/schema/Calibrate")
        self.assertEqual(resp.status_code, 200)
        names = [s["name"] for s in resp.get_json()["subprocesses"]]
        self.assertEqual(names, ["bias_subtraction", "dark_subtraction", "flat_fielding"])

    def test_unknown_process_schema_404(self) -> None:
        self.assertEqual(self.client.get("/api/schema/Nope").status_code, 404)

    # -- run --------------------------------------------------------------

    def test_run_calibrate_persists_output(self) -> None:
        img = ImageData.from_frames(
            lights=[_light(100.0, exptime=200)],
            bias=[_light(10.0)],
            darks=[_light(5.0, exptime=100)],
            flats=[_light(4.0)],
        )
        self._seed_upload(img)
        resp = self.client.post(
            "/api/run",
            json={
                "process": "Calibrate",
                "configs": {
                    "dark_subtraction": {"algorithm": "subtract", "params": {"scale": True}}
                },
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["process"], "Calibrate")
        out = self.app.extensions["pmo_store"].get(self.sid, "Calibrate")
        self.assertIsNotNone(out)
        self.assertEqual(float(out.lights["R"][0].data.mean()), 80.0)

    def test_run_chains_calibrate_then_stack(self) -> None:
        # No calibration frames -> Calibrate is a no-op; Stack then medians the lights.
        self._seed_upload(ImageData.from_frames([_light(1.0), _light(3.0), _light(11.0)]))
        self.client.post("/api/run", json={"process": "Calibrate", "configs": {}})
        resp = self.client.post(
            "/api/run",
            json={
                "process": "Stack",
                "configs": {
                    "outlier_rejection": {"algorithm": "none"},
                    "coaddition": {"algorithm": "median"},
                },
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["stacked"])
        out = self.app.extensions["pmo_store"].get(self.sid, "Stack")
        self.assertEqual(float(out.lights["R"][0].data.mean()), 3.0)  # median(1,3,11)

    def test_run_without_input_returns_409(self) -> None:
        with self.client.session_transaction() as sess:
            sess["session_id"] = "empty-session"
        resp = self.client.post("/api/run", json={"process": "Calibrate", "configs": {}})
        self.assertEqual(resp.status_code, 409)

    def test_run_before_previous_step_returns_409(self) -> None:
        # Stack needs Calibrate's output; with only an upload seeded it has none.
        self._seed_upload(ImageData.from_frames([_light(1.0), _light(3.0)]))
        resp = self.client.post(
            "/api/run", json={"process": "Stack", "configs": {}}
        )
        self.assertEqual(resp.status_code, 409)

    def test_run_unknown_process_returns_404(self) -> None:
        self.assertEqual(
            self.client.post("/api/run", json={"process": "Nope"}).status_code, 404
        )

    def test_run_invalid_param_returns_400(self) -> None:
        img = ImageData.from_frames(
            lights=[_light(100.0, exptime=10)], darks=[_light(5.0, exptime=10)]
        )
        self._seed_upload(img)
        resp = self.client.post(
            "/api/run",
            json={
                "process": "Calibrate",
                "configs": {
                    "dark_subtraction": {"algorithm": "subtract", "params": {"scale": "maybe"}}
                },
            },
        )
        self.assertEqual(resp.status_code, 400)


if __name__ == "__main__":
    unittest.main()
