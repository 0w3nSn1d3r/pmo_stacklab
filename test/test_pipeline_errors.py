"""Tests for friendly, user-actionable pipeline errors (PipelineError -> 422)."""
from __future__ import annotations

import unittest

import numpy as np
from astropy.nddata import CCDData

from pmo_stacklab.app.factory import build_app
from pmo_stacklab.app.blueprints.process import UPLOAD_KEY
from pmo_stacklab.modules.core import ImageData, PipelineError
from pmo_stacklab.modules.reprojection import build_reproject, build_warp, build_wcs
from pmo_stacklab.modules.stacking import build_stack, no_rejection
from pmo_stacklab.modules.stacking.coaddition import Coaddition


def _light(value: float, *, filt: str = "R", shape=(4, 4)) -> CCDData:
    return CCDData(np.full(shape, float(value)), unit="adu", meta={"FILTER": filt})


class ScienceLayerTests(unittest.TestCase):
    def test_stacking_mismatched_shapes_raises_pipeline_error(self) -> None:
        img = ImageData.from_frames(
            [_light(1.0, shape=(4, 4)), _light(2.0, shape=(8, 8))]
        )
        process = build_stack(no_rejection, Coaddition.build_mean())
        with self.assertRaises(PipelineError) as ctx:
            process.run(img)
        self.assertIn("different sizes", str(ctx.exception))

    def test_wcs_registration_without_wcs_raises_pipeline_error(self) -> None:
        img = ImageData.from_frames([_light(1.0), _light(2.0)])
        process = build_reproject(build_wcs(), build_warp("nearest"))
        with self.assertRaises(PipelineError) as ctx:
            process.run(img)
        self.assertIn("WCS", str(ctx.exception))


class EndpointTranslationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = build_app()
        self.client = self.app.test_client()
        with self.client.session_transaction() as sess:
            sess["session_id"] = "err-session"

    def _seed(self, img: ImageData) -> None:
        self.app.extensions["pmo_store"].put("err-session", UPLOAD_KEY, img)

    def test_run_returns_422_with_actionable_message(self) -> None:
        # Mismatched light frames reach Stack via the endpoint.
        self._seed(ImageData.from_frames([_light(1.0, shape=(4, 4)), _light(2.0, shape=(8, 8))]))
        # Calibrate (no-op) then Reproject (none) keep the differing sizes, so Stack
        # raises. Run them in order through the endpoint.
        self.client.post("/api/run", json={"process": "Calibrate", "configs": {}})
        self.client.post(
            "/api/run",
            json={
                "process": "Reproject",
                "configs": {
                    "registration": {"algorithm": "none"},
                    "alignment": {"algorithm": "nearest"},
                },
            },
        )
        resp = self.client.post(
            "/api/run",
            json={"process": "Stack", "configs": {"outlier_rejection": {"algorithm": "none"}, "coaddition": {"algorithm": "mean"}}},
        )
        self.assertEqual(resp.status_code, 422)
        self.assertIn("different sizes", resp.get_json()["error"])

    def test_quickstack_run_returns_422_naming_the_process(self) -> None:
        self._seed(ImageData.from_frames([_light(1.0), _light(2.0)]))
        # Force WCS registration on frames without a WCS -> Reproject raises.
        recipe = self.client.get("/api/quickstack").get_json()["recipe"]
        recipe["Reproject"]["registration"] = {"algorithm": "wcs", "params": {}}
        self.client.put("/api/quickstack", json=recipe)
        resp = self.client.post("/api/quickstack/run")
        self.assertEqual(resp.status_code, 422)
        self.assertTrue(resp.get_json()["error"].startswith("Reproject"))


if __name__ == "__main__":
    unittest.main()
