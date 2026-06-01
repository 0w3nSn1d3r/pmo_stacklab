"""Tests for the Quick Stack config store and the /api/quickstack routes."""
from __future__ import annotations

import os
import tempfile
import unittest

import numpy as np
from astropy.nddata import CCDData

from pmo_stacklab.app.factory import build_app
from pmo_stacklab.app.blueprints.process import UPLOAD_KEY
from pmo_stacklab.app import quickstack
from pmo_stacklab.modules.core import ImageData


def _light(value: float, *, filt: str = "R", exptime: float | None = None) -> CCDData:
    meta: dict[str, object] = {"FILTER": filt}
    if exptime is not None:
        meta["EXPTIME"] = exptime
    return CCDData(np.full((6, 6), float(value), dtype=float), unit="adu", meta=meta)


class RecipeStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "sub", "quickstack.json")  # nested -> tests mkdir

    def test_missing_file_returns_default(self) -> None:
        recipe = quickstack.load_recipe(self.path)
        self.assertIn("Stack", recipe)
        self.assertEqual(recipe["Stack"]["outlier_rejection"]["algorithm"], "sigma_clip")

    def test_save_then_load_roundtrip(self) -> None:
        recipe = quickstack.default_recipe()
        recipe["Stack"]["coaddition"]["algorithm"] = "median"
        quickstack.save_recipe(self.path, recipe)
        self.assertTrue(os.path.exists(self.path))
        loaded = quickstack.load_recipe(self.path)
        self.assertEqual(loaded["Stack"]["coaddition"]["algorithm"], "median")

    def test_reset_restores_default(self) -> None:
        quickstack.save_recipe(self.path, {"Stack": {"coaddition": {"algorithm": "median"}}})
        recipe = quickstack.reset_recipe(self.path)
        self.assertEqual(recipe["Stack"]["coaddition"]["algorithm"], "mean")
        # And it was persisted.
        self.assertEqual(
            quickstack.load_recipe(self.path)["Stack"]["coaddition"]["algorithm"], "mean"
        )

    def test_corrupt_file_falls_back_to_default(self) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("{ not json")
        self.assertIn("Calibrate", quickstack.load_recipe(self.path))


class QuickStackRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "quickstack.json")
        self.app = build_app({"QUICKSTACK_CONFIG_PATH": self.path})
        self.client = self.app.test_client()
        with self.client.session_transaction() as sess:
            sess["session_id"] = "qs-session"

    def _seed_upload(self) -> None:
        img = ImageData.from_frames(
            lights=[_light(100.0, exptime=200), _light(108.0, exptime=200)],
            bias=[_light(10.0)],
            darks=[_light(5.0, exptime=100)],
        )
        self.app.extensions["pmo_store"].put("qs-session", UPLOAD_KEY, img)

    def test_get_config_returns_recipe_and_schema(self) -> None:
        resp = self.client.get("/api/quickstack")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertIn("Stack", body["recipe"])
        names = [p["name"] for p in body["schema"]["processes"]]
        self.assertEqual(names, ["Calibrate", "Reproject", "Stack", "Post-Process"])

    def test_save_and_persist_config(self) -> None:
        recipe = quickstack.default_recipe()
        recipe["Stack"]["coaddition"]["algorithm"] = "median"
        resp = self.client.put("/api/quickstack", json=recipe)
        self.assertEqual(resp.status_code, 200)
        # Reloading reflects the saved choice.
        again = self.client.get("/api/quickstack").get_json()
        self.assertEqual(again["recipe"]["Stack"]["coaddition"]["algorithm"], "median")

    def test_save_invalid_recipe_rejected(self) -> None:
        resp = self.client.put("/api/quickstack", json={"Stack": {"coaddition": {"algorithm": "nope"}}})
        self.assertEqual(resp.status_code, 400)

    def test_reset_config(self) -> None:
        self.client.put(
            "/api/quickstack",
            json={**quickstack.default_recipe(), "Stack": {"coaddition": {"algorithm": "median"}}},
        )
        resp = self.client.post("/api/quickstack/reset")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.get_json()["recipe"]["Stack"]["coaddition"]["algorithm"], "mean"
        )

    def test_run_requires_upload(self) -> None:
        resp = self.client.post("/api/quickstack/run")
        self.assertEqual(resp.status_code, 409)

    def test_run_applies_whole_pipeline_and_persists_steps(self) -> None:
        self._seed_upload()
        # Use a simple, deterministic recipe (no registration so values are exact).
        recipe = quickstack.default_recipe()
        recipe["Reproject"]["registration"] = {"algorithm": "none", "params": {}}
        recipe["Reproject"]["alignment"] = {"algorithm": "nearest", "params": {}}
        recipe["Stack"]["outlier_rejection"] = {"algorithm": "none", "params": {}}
        recipe["Stack"]["coaddition"] = {"algorithm": "mean", "params": {}}
        # Post-Process would normalize to [0,1]; drop it so we can check arithmetic.
        recipe["Post-Process"]["background"] = {"algorithm": "none", "params": {}}
        recipe["Post-Process"]["intensity_scaling"] = {"algorithm": "minmax", "params": {}}
        recipe["Post-Process"]["stretch"] = {"algorithm": "linear", "params": {}}
        self.client.put("/api/quickstack", json=recipe)

        resp = self.client.post("/api/quickstack/run")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["process"], "Post-Process")

        store = self.app.extensions["pmo_store"]
        # Each step persisted, so per-step preview/metrics work afterwards.
        for step in ("Calibrate", "Reproject", "Stack", "Post-Process"):
            self.assertIsNotNone(store.get("qs-session", step), step)
        # Calibrate output: (100,108) -bias10 -dark(5*2) -> (80,88); stacked mean 84.
        self.assertEqual(float(store.get("qs-session", "Stack").lights["R"][0].data.mean()), 84.0)


if __name__ == "__main__":
    unittest.main()
