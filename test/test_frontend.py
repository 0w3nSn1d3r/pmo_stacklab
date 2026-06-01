"""Tests that the pages are wired to the schema-driven frontend.

These verify server-side wiring -- that each process page mounts the config
container for the right process, that pages load their module entry points and the
stylesheet, and that the static assets are served. They do not execute JavaScript;
rendered behaviour is verified in a browser.
"""
from __future__ import annotations

import unittest

from pmo_stacklab.app.factory import build_app


class ProcessPageWiringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = build_app().test_client()

    def test_pages_mount_correct_process(self) -> None:
        cases = {
            "/calibrate": "Calibrate",
            "/stack": "Stack",
            "/reproject": "Reproject",
            "/postprocess": "Post-Process",
        }
        for route, process in cases.items():
            resp = self.client.get(route)
            self.assertEqual(resp.status_code, 200, route)
            html = resp.get_data(as_text=True)
            self.assertIn(f'data-process="{process}"', html, route)
            self.assertIn("js/process-page.js", html, route)
            self.assertIn("css/styles.css", html, route)
            self.assertIn('id="navbar"', html, route)

    def test_home_and_upload_wired(self) -> None:
        home = self.client.get("/").get_data(as_text=True)
        self.assertIn("js/home.js", home)
        self.assertIn('id="navbar"', home)

        upload = self.client.get("/upload").get_data(as_text=True)
        self.assertIn("js/upload-page.js", upload)
        # The upload form must expose the four /api/upload multipart fields.
        for field in ("lights", "darks", "bias", "flats"):
            self.assertIn(f'name="{field}"', upload)

        color = self.client.get("/color").get_data(as_text=True)
        self.assertIn("js/color-page.js", color)
        self.assertIn('id="navbar"', color)
        self.assertIn('id="color-download"', color)  # download menu present

        # Upload page exposes the Quick Stack button and its settings menu.
        upload_html = self.client.get("/upload").get_data(as_text=True)
        self.assertIn('id="quick-stack"', upload_html)
        self.assertIn('id="qs-configure"', upload_html)
        self.assertIn('id="qs-reset"', upload_html)
        self.assertIn("quickstack=1", upload_html)  # Configure enters config mode


class StaticAssetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = build_app().test_client()

    def test_frontend_assets_served(self) -> None:
        for asset in (
            "/static/js/api.js",
            "/static/js/info-tip.js",
            "/static/js/config-menu.js",
            "/static/js/preview-panel.js",
            "/static/js/nav.js",
            "/static/js/process-page.js",
            "/static/js/upload-page.js",
            "/static/js/color-page.js",
            "/static/js/home.js",
            "/static/css/styles.css",
        ):
            resp = self.client.get(asset)
            self.assertEqual(resp.status_code, 200, asset)
            resp.close()

    def test_modules_use_relative_imports(self) -> None:
        # process-page.js must import its siblings by relative path so the browser
        # resolves them under /static/js/.
        resp = self.client.get("/static/js/process-page.js")
        js = resp.get_data(as_text=True)
        resp.close()
        self.assertIn('from "./api.js"', js)
        self.assertIn('"./config-menu.js"', js)


if __name__ == "__main__":
    unittest.main()
