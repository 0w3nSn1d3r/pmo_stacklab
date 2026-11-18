"""Tests for colour combination (core.color_combine) and the /api/color routes.

Frames carry a ramp rather than a constant: normalization is defined by the
spread of a frame's own values, so a uniform frame legitimately normalizes to
black and would make these assertions vacuous.
"""
from __future__ import annotations

import unittest

import numpy as np
from astropy.nddata import CCDData

from pmo_stacklab.app.factory import build_app
from pmo_stacklab.app.blueprints.process import COLOR_KEY, UPLOAD_KEY
from pmo_stacklab.modules.core import (
    COLOR_COMBINE,
    LUMINANCE_APPLY,
    NORMALIZATION,
    ImageData,
    RGBImage,
    apply_gain,
    build_minmax_normalizer,
    combine_image_data,
    mix_colors,
    normalize_plane,
    parse_color,
)
from pmo_stacklab.modules.core.color_combine import build_linear, build_lupton

RED, GREEN, BLUE = "#ff0000", "#00ff00", "#0000ff"


def _ramp(scale: float, shape=(8, 8)) -> np.ndarray:
    """A 2-D ramp spanning 0..scale, so the frame has a real dynamic range."""
    return np.linspace(0.0, scale, num=shape[0] * shape[1]).reshape(shape)


def _stacked(values: dict[str, float], shape=(8, 8)) -> ImageData:
    """A stacked ImageData: one ramped frame per filter, peaking at the value."""
    frames = [
        CCDData(_ramp(v, shape), unit="adu", meta={"FILTER": f})
        for f, v in values.items()
    ]
    return ImageData.from_frames(frames)


class ParseColorTests(unittest.TestCase):
    def test_parses_full_and_shorthand(self) -> None:
        self.assertEqual(parse_color("#ff0000"), (1.0, 0.0, 0.0))
        self.assertEqual(parse_color("00ff00"), (0.0, 1.0, 0.0))
        self.assertEqual(parse_color("#f00"), (1.0, 0.0, 0.0))

    def test_rejects_malformed(self) -> None:
        for bad in ("#12345", "red", "", None, 0xFF0000, "#gggggg"):
            with self.assertRaises(ValueError):
                parse_color(bad)


class NormalizeTests(unittest.TestCase):
    def test_single_hot_pixel_does_not_crush_the_frame(self) -> None:
        # Regression: min-max normalization divided by the brightest pixel, so a
        # saturated star core pushed the sky to ~0.004 and every allowed Lupton
        # stretch rendered black. A percentile span must keep real signal near 1.
        plane = np.full((64, 64), 250.0)  # sky dominates, as on a real frame
        plane[:, 60:] = 400.0  # a little real structure
        plane[0, 0] = 65535.0  # saturated star
        out = normalize_plane(plane)
        self.assertGreater(float(np.median(out[:, 60:])), 0.5)
        self.assertGreater(float(out.max()), 1.0)  # bright tail left uncompressed

    def test_uniform_plane_is_black_not_nan(self) -> None:
        out = normalize_plane(np.full((4, 4), 7.0))
        self.assertTrue(np.all(out == 0.0))

    def test_sky_lands_at_the_same_level_whatever_the_frame(self) -> None:
        # The property that keeps a combine's background neutral: filters differ
        # wildly in sky level, depth and noise, and all of them must put their
        # background at the same place on the normalized scale.
        rng = np.random.default_rng(0)
        for sky, noise, signal in ((204.0, 4.0, 12.0), (311.0, 30.0, 260.0),
                                   (238.0, 14.0, 110.0)):
            plane = rng.normal(sky, noise, size=(256, 256))
            plane[:8] += signal  # a little real structure in the bright tail
            self.assertAlmostEqual(
                float(np.median(normalize_plane(plane))), 0.05, delta=0.01
            )

    def test_a_noisy_shallow_filter_does_not_tint_the_background(self) -> None:
        # Regression: anchoring the low end on a percentile let a filter whose
        # noise was large relative to its own range (real M33 R data) sit ~3x
        # higher than the others, so the sky came out red.
        rng = np.random.default_rng(1)
        shallow = rng.normal(204.0, 4.0, size=(256, 256))   # thin range, noisy
        deep = rng.normal(311.0, 30.0, size=(256, 256))     # wide range
        planes = {"R": normalize_plane(shallow), "V": normalize_plane(deep)}
        r, g, _ = mix_colors(planes, {"R": RED, "V": GREEN})
        self.assertAlmostEqual(float(np.median(r)), float(np.median(g)), delta=0.02)


class NormalizationChoiceTests(unittest.TestCase):
    """The normalization choice is a declared, juxtaposable Subprocess."""

    def _sky_levels(self, algorithm: str, **params) -> tuple[float, float]:
        """Sky level of a shallow and a deep frame after normalization.

        Modelled on the real M33 R and V stacks. What separates them is how far
        the signal tail reaches in units of the frame's own noise -- R's reached
        ~5 sigma above sky, V's ~19 -- not the noise or sky level themselves,
        which a percentile ratio is blind to.
        """
        rng = np.random.default_rng(2)
        shallow = rng.normal(204.0, 2.2, size=(256, 256))
        shallow[:, :3] += 12.0  # short tail
        deep = rng.normal(311.0, 14.0, size=(256, 256))
        deep[:, :3] += 264.0  # long tail
        normalize = NORMALIZATION.build(algorithm, params)
        return float(np.median(normalize(shallow))), float(np.median(normalize(deep)))

    def test_offers_the_three_options_and_defaults_to_sky(self) -> None:
        self.assertEqual(
            [a.name for a in NORMALIZATION.algorithms],
            ["minmax", "percentile", "sky"],
        )
        self.assertEqual(NORMALIZATION.default_algorithm.name, "sky")

    def test_sky_equalizes_backgrounds_but_percentile_does_not(self) -> None:
        # The pedagogical point of putting this choice in front of the user.
        sky_a, sky_b = self._sky_levels("sky")
        self.assertAlmostEqual(sky_a, sky_b, delta=0.01)
        pct_a, pct_b = self._sky_levels("percentile")
        self.assertGreater(abs(pct_a - pct_b), 0.05)

    def test_minmax_crushes_a_frame_with_a_saturated_star(self) -> None:
        plane = np.full((64, 64), 250.0)
        plane[0, 0] = 65535.0
        out = build_minmax_normalizer()(plane)
        self.assertLess(float(np.median(out)), 0.01)

    def test_sky_level_parameter_moves_the_background(self) -> None:
        normalize = NORMALIZATION.build("sky", {"sky_level": 0.2})
        rng = np.random.default_rng(3)
        plane = rng.normal(300.0, 20.0, size=(128, 128))
        self.assertAlmostEqual(float(np.median(normalize(plane))), 0.2, delta=0.01)


class GainTests(unittest.TestCase):
    def test_gain_scales_signal_and_leaves_the_background_alone(self) -> None:
        # A plain multiply would drag the background up with the signal and
        # re-tint the sky; the gain must pivot about the background.
        plane = np.full((32, 32), 0.05)
        plane[:4] = 0.55  # signal, 0.5 above background
        out = apply_gain(plane, 2.0)
        self.assertAlmostEqual(float(np.median(out)), 0.05, places=6)
        self.assertAlmostEqual(float(out[0, 0]), 0.05 + 1.0, places=6)

    def test_gain_of_one_is_identity(self) -> None:
        plane = np.linspace(0, 1, 64).reshape(8, 8)
        self.assertTrue(np.array_equal(apply_gain(plane, 1.0), plane))

    def test_gains_do_not_tint_the_background(self) -> None:
        planes = {"R": np.full((16, 16), 0.05), "V": np.full((16, 16), 0.05)}
        planes["R"][:2] = 0.6
        planes["V"][:2] = 0.6
        r, g, _ = mix_colors(planes, {"R": RED, "V": GREEN}, {"R": 3.0, "V": 1.0})
        self.assertAlmostEqual(float(np.median(r)), float(np.median(g)), places=6)
        self.assertGreater(float(r[0, 0]), float(g[0, 0]))  # signal did change


class MixTests(unittest.TestCase):
    def test_primaries_land_in_their_own_channel(self) -> None:
        planes = {"R": np.full((2, 2), 1.0), "B": np.full((2, 2), 0.5)}
        r, g, b = mix_colors(planes, {"R": RED, "B": BLUE})
        self.assertTrue(np.allclose(r, 1.0))
        self.assertTrue(np.allclose(g, 0.0))  # nothing assigned green
        self.assertTrue(np.allclose(b, 0.5))

    def test_two_filters_on_one_colour_average_rather_than_double(self) -> None:
        planes = {"Ha": np.full((2, 2), 1.0), "SII": np.full((2, 2), 0.0)}
        r, _, _ = mix_colors(planes, {"Ha": RED, "SII": RED})
        self.assertTrue(np.allclose(r, 0.5))

    def test_one_filter_can_feed_two_channels(self) -> None:
        # A single cyan OIII is the HOO palette's green+blue, expressed directly.
        planes = {"OIII": np.full((2, 2), 0.8)}
        r, g, b = mix_colors(planes, {"OIII": "#00ffff"})
        self.assertTrue(np.allclose(r, 0.0))
        self.assertTrue(np.allclose(g, 0.8))
        self.assertTrue(np.allclose(b, 0.8))


class CombineTests(unittest.TestCase):
    def test_combines_three_filters(self) -> None:
        img = _stacked({"R": 100.0, "G": 50.0, "B": 10.0})
        rgb = combine_image_data(
            img, {"R": RED, "G": GREEN, "B": BLUE}, build_linear()
        )
        self.assertIsInstance(rgb, RGBImage)
        self.assertEqual(rgb.data.shape, (8, 8, 3))
        self.assertEqual(rgb.data.dtype, np.uint8)
        self.assertEqual(rgb.colors["R"], RED)
        self.assertIsNone(rgb.luminance)

    def test_supports_more_than_three_filters(self) -> None:
        img = _stacked({"Ha": 100.0, "OIII": 80.0, "SII": 60.0, "R": 40.0, "B": 20.0})
        rgb = combine_image_data(
            img,
            {
                "Ha": "#ff2000",
                "OIII": "#00ffc0",
                "SII": "#ff0040",
                "R": RED,
                "B": BLUE,
            },
            build_lupton(),
        )
        self.assertEqual(rgb.data.shape, (8, 8, 3))
        self.assertEqual(len(rgb.colors), 5)

    def test_supports_a_single_filter(self) -> None:
        img = _stacked({"Ha": 100.0})
        rgb = combine_image_data(img, {"Ha": RED}, build_linear())
        self.assertEqual(int(rgb.data[..., 1].max()), 0)  # green stays black
        self.assertGreater(int(rgb.data[..., 0].max()), 0)

    def test_lupton_default_is_not_a_black_image(self) -> None:
        # Regression: with min-max normalization the shipped defaults produced a
        # fully black image from linear stacked data.
        img = _stacked({"R": 60000.0, "G": 50000.0, "B": 40000.0}, shape=(64, 64))
        combiner = COLOR_COMBINE.build("lupton")  # declared defaults
        rgb = combine_image_data(img, {"R": RED, "G": GREEN, "B": BLUE}, combiner)
        self.assertGreater(float(np.asarray(rgb.data).mean()), 20.0)

    def test_requires_at_least_one_colour(self) -> None:
        img = _stacked({"R": 100.0})
        with self.assertRaises(ValueError):
            combine_image_data(img, {}, build_linear())

    def test_unknown_filter_raises(self) -> None:
        img = _stacked({"R": 100.0})
        with self.assertRaises(ValueError):
            combine_image_data(img, {"Z": RED}, build_linear())

    def test_bad_colour_raises(self) -> None:
        img = _stacked({"R": 100.0})
        with self.assertRaises(ValueError):
            combine_image_data(img, {"R": "crimson"}, build_linear())

    def test_unstacked_filter_raises(self) -> None:
        frames = [
            CCDData(_ramp(1.0), unit="adu", meta={"FILTER": "R"}),
            CCDData(_ramp(1.0), unit="adu", meta={"FILTER": "R"}),
        ]
        img = ImageData.from_frames(frames)
        with self.assertRaises(ValueError):
            combine_image_data(img, {"R": RED}, build_linear())

    def test_mismatched_shapes_raise(self) -> None:
        frames = [
            CCDData(_ramp(1.0, (8, 8)), unit="adu", meta={"FILTER": "R"}),
            CCDData(_ramp(1.0, (4, 4)), unit="adu", meta={"FILTER": "G"}),
        ]
        img = ImageData.from_frames(frames)
        with self.assertRaises(ValueError):
            combine_image_data(img, {"R": RED, "G": GREEN}, build_linear())


class LuminanceTests(unittest.TestCase):
    def _combine(self, algorithm: str | None, amount: float = 1.0) -> RGBImage:
        img = _stacked({"R": 100.0, "G": 50.0, "B": 10.0, "L": 400.0}, shape=(32, 32))
        colors = {"R": RED, "G": GREEN, "B": BLUE}
        if algorithm is None:
            return combine_image_data(img, colors, build_linear())
        return combine_image_data(
            img,
            colors,
            build_linear(),
            luminance_filter="L",
            luminance=LUMINANCE_APPLY.build(algorithm, {"amount": amount}),
        )

    def test_luminance_is_recorded_and_changes_the_image(self) -> None:
        plain = self._combine(None)
        lit = self._combine("lab")
        self.assertIsNone(plain.luminance)
        self.assertEqual(lit.luminance, "L")
        self.assertFalse(np.array_equal(plain.data, lit.data))

    def test_amount_zero_leaves_the_image_alone(self) -> None:
        plain = self._combine(None)
        none_applied = self._combine("lab", amount=0.0)
        # A zero blend must be a no-op bar colour-space round-trip rounding.
        diff = np.abs(plain.data.astype(int) - none_applied.data.astype(int))
        self.assertLessEqual(int(diff.max()), 2)

    def test_hsv_is_offered_alongside_lab(self) -> None:
        self.assertEqual(
            [a.name for a in LUMINANCE_APPLY.algorithms], ["lab", "hsv"]
        )
        self.assertEqual(LUMINANCE_APPLY.default_algorithm.name, "lab")

    def test_unknown_luminance_filter_raises(self) -> None:
        img = _stacked({"R": 100.0})
        with self.assertRaises(ValueError):
            combine_image_data(
                img,
                {"R": RED},
                build_linear(),
                luminance_filter="Z",
                luminance=LUMINANCE_APPLY.build("lab", {}),
            )


class ColorRouteTests(unittest.TestCase):
    def setUp(self) -> None:
        self.app = build_app()
        self.client = self.app.test_client()
        with self.client.session_transaction() as sess:
            sess["session_id"] = "color-session"
        img = _stacked({"R": 100.0, "V": 50.0, "B": 10.0, "Lum": 400.0})
        self.app.extensions["pmo_store"].put("color-session", UPLOAD_KEY, img)

    def test_schema_lists_filters_and_default_colours(self) -> None:
        resp = self.client.get("/api/color")
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(set(body["filters"]), {"R", "V", "B", "Lum"})
        # V stands in for green in a photometric set; Lum is luminance, not colour.
        self.assertEqual(body["default_colors"]["R"], "#ff0000")
        self.assertEqual(body["default_colors"]["V"], "#00ff00")
        self.assertNotIn("Lum", body["default_colors"])
        self.assertEqual(body["default_luminance"], "Lum")
        self.assertEqual(body["combine"]["default"], "lupton")
        self.assertEqual(body["luminance"]["default"], "lab")
        self.assertEqual(body["normalization"]["default"], "sky")
        self.assertEqual(body["default_gains"], {"R": 1.0, "V": 1.0, "B": 1.0})
        self.assertEqual(body["gain_range"], [0.0, 4.0])

    def test_unknown_filter_names_get_spread_hues(self) -> None:
        img = _stacked({"F438W": 1.0, "F555W": 2.0, "F814W": 3.0})
        self.app.extensions["pmo_store"].put("color-session", UPLOAD_KEY, img)
        colors = self.client.get("/api/color").get_json()["default_colors"]
        self.assertEqual(len(colors), 3)
        self.assertEqual(len(set(colors.values())), 3)  # all distinct

    def _combine(self, **extra) -> None:
        body = {"algorithm": "linear", "colors": {"R": RED, "V": GREEN, "B": BLUE}}
        body.update(extra)
        return self.client.post("/api/color", json=body)

    def test_combine_then_fetch_png(self) -> None:
        resp = self._combine()
        self.assertEqual(resp.status_code, 200, resp.get_json())
        self.assertEqual(resp.get_json()["colors"]["R"], RED)
        stored = self.app.extensions["pmo_store"].get("color-session", COLOR_KEY)
        self.assertIsInstance(stored, RGBImage)

        png = self.client.get("/api/color.png")
        self.assertEqual(png.status_code, 200)
        self.assertEqual(png.get_data()[:8], b"\x89PNG\r\n\x1a\n")

    def test_combine_with_luminance(self) -> None:
        resp = self._combine(
            luminance={"filter": "Lum", "algorithm": "lab", "params": {"amount": 0.8}}
        )
        self.assertEqual(resp.status_code, 200, resp.get_json())
        self.assertEqual(resp.get_json()["luminance"], "Lum")

    def test_png_before_combine_404(self) -> None:
        self.assertEqual(self.client.get("/api/color.png").status_code, 404)

    def test_combine_bad_filter_400(self) -> None:
        self.assertEqual(self._combine(colors={"Z": RED}).status_code, 400)

    def test_combine_accepts_gains_and_normalization(self) -> None:
        resp = self._combine(
            gains={"R": 1.5, "V": 1.0, "B": 0.8},
            normalization={"algorithm": "percentile", "params": {"low": 2.0}},
        )
        self.assertEqual(resp.status_code, 200, resp.get_json())
        self.assertEqual(resp.get_json()["gains"]["R"], 1.5)

    def test_out_of_range_gain_400(self) -> None:
        resp = self._combine(gains={"R": 99.0})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("gain", resp.get_json()["error"])

    def test_non_numeric_gain_400(self) -> None:
        self.assertEqual(self._combine(gains={"R": "loud"}).status_code, 400)

    def test_unknown_normalization_algorithm_400(self) -> None:
        resp = self._combine(normalization={"algorithm": "nope"})
        self.assertEqual(resp.status_code, 400)

    def test_combine_bad_colour_400(self) -> None:
        self.assertEqual(self._combine(colors={"R": "nope"}).status_code, 400)

    def test_schema_409_when_nothing_stacked(self) -> None:
        with self.client.session_transaction() as sess:
            sess["session_id"] = "empty-color-session"
        self.assertEqual(self.client.get("/api/color").status_code, 409)

    def test_download_png(self) -> None:
        self._combine()
        resp = self.client.get("/api/color/download.png")
        self.assertEqual(resp.status_code, 200)
        self.assertIn("StackLab_color.png", resp.headers["Content-Disposition"])
        self.assertEqual(resp.get_data()[:8], b"\x89PNG\r\n\x1a\n")

    def test_download_fits_records_every_filter_and_colour(self) -> None:
        import io as _io
        from astropy.io import fits

        self._combine(
            luminance={"filter": "Lum", "algorithm": "lab", "params": {}}
        )
        resp = self.client.get("/api/color/download.fits")
        self.assertEqual(resp.status_code, 200)
        header = fits.open(_io.BytesIO(resp.get_data()))[0].header
        recorded = {
            header[f"FILT{i}"]: header[f"COLR{i}"] for i in (1, 2, 3)
        }
        self.assertEqual(recorded, {"R": RED, "V": GREEN, "B": BLUE})
        self.assertEqual(header["LUMFILT"], "Lum")

    def test_download_before_combine_404(self) -> None:
        self.assertEqual(self.client.get("/api/color/download.png").status_code, 404)

    def test_download_unknown_format_400(self) -> None:
        self._combine()
        self.assertEqual(self.client.get("/api/color/download.tiff").status_code, 400)


if __name__ == "__main__":
    unittest.main()
