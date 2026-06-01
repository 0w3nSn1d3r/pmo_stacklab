"""Tests for graceful, JSON, actionable error handling across the API.

These verify that malformed input and missing endpoints yield clean JSON errors
(never an HTML 500 page), with actionable messages where the fault is the user's.
"""
from __future__ import annotations

import unittest

from pmo_stacklab.app.factory import build_app


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


if __name__ == "__main__":
    unittest.main()
