"""Tests for the Reproject process: registration, alignment, and the pipeline.

Synthetic star fields with a known offset stand in for real frames. The key
property a correct registration+alignment must have is that a shifted frame, once
reprojected onto the reference, lines its stars back up with the reference -- which
we check by the alignment sharpening the eventual mean of the two frames.
"""
from __future__ import annotations

import unittest

import numpy as np
from astropy.nddata import CCDData
from astropy.wcs import WCS

from pmo_stacklab.modules.core import ImageData, PipelineError
from pmo_stacklab.modules.reprojection import (
    ALIGNMENT,
    REGISTRATION,
    REPROJECT,
    build_astroalign,
    build_none,
    build_phase_correlation,
    build_reproject,
    build_warp,
    build_wcs,
)

_STARS = [(15, 20), (40, 50), (30, 12), (50, 25), (22, 45), (10, 55), (45, 38),
          (18, 33), (35, 28), (52, 48), (28, 58), (48, 14), (12, 40), (38, 8)]


def _star_field(shift=(0, 0), shape=(64, 64), filt="R", wcs=None) -> CCDData:
    """A noiseless star field; stars (3x3 Gaussian-ish blobs) planted at fixed
    positions plus ``shift``. Bright and dense enough that a few-pixel shift
    produces unambiguous misalignment."""
    img = np.full(shape, 10.0)
    for (r, c) in _STARS:
        rr, cc = r + shift[0], c + shift[1]
        if 2 <= rr < shape[0] - 2 and 2 <= cc < shape[1] - 2:
            # A small peaked blob so star cores overlap poorly when misaligned.
            img[rr, cc] += 1000
            img[rr + 1, cc] += 400
            img[rr - 1, cc] += 400
            img[rr, cc + 1] += 400
            img[rr, cc - 1] += 400
    return CCDData(img, unit="adu", meta={"FILTER": filt}, wcs=wcs)


def _misalignment(frames) -> float:
    """Mean abs difference between the two frames -- 0 when perfectly aligned."""
    a, b = np.asarray(frames[0].data), np.asarray(frames[1].data)
    return float(np.abs(a - b).mean())


class AlignmentTests(unittest.TestCase):
    def test_unknown_interpolation_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_warp("sinc")

    def test_warp_marks_offgrid_pixels_in_mask(self) -> None:
        # Shift content far enough that some reference pixels map off the source.
        frame = _star_field((0, 0))
        align = build_warp("nearest")

        def shift_map(coords):
            out = np.asarray(coords, dtype=float).copy()
            out[:, 0] -= 20  # pull x sources 20px right -> left edge falls off
            return out

        out = align(frame, shift_map)
        self.assertIsNotNone(out.mask)
        self.assertTrue(out.mask.any())  # some pixels flagged invalid


class RegistrationTests(unittest.TestCase):
    def _reproject(self, register, align=None):
        ref = _star_field((0, 0))
        moved = _star_field((5, -3))
        img = ImageData.from_frames([ref, moved])
        out = build_reproject(register, align or build_warp("bilinear")).run(img)
        return img, out

    def test_none_leaves_misalignment(self) -> None:
        # Baseline: "none" must not improve alignment, whereas a real registration
        # (astroalign) markedly does -- so "none" misalignment is much the larger.
        _, none_out = self._reproject(build_none())
        _, aligned_out = self._reproject(build_astroalign())
        self.assertGreater(
            _misalignment(none_out.lights["R"]),
            _misalignment(aligned_out.lights["R"]) * 5,
        )

    def test_astroalign_aligns(self) -> None:
        img, out = self._reproject(build_astroalign())
        before = _misalignment(img.lights["R"])
        after = _misalignment(out.lights["R"])
        self.assertLess(after, before * 0.5)  # alignment markedly reduces mismatch

    def test_phase_correlation_aligns_pure_translation(self) -> None:
        img, out = self._reproject(build_phase_correlation())
        self.assertLess(_misalignment(out.lights["R"]), _misalignment(img.lights["R"]) * 0.5)

    def test_reference_frame_is_unchanged(self) -> None:
        _, out = self._reproject(build_astroalign())
        # Frame 0 is the reference: identity-mapped, so its stars stay put.
        ref_out = np.asarray(out.lights["R"][0].data)
        self.assertGreater(ref_out.max(), 400)

    def test_wcs_registration_requires_wcs(self) -> None:
        img = ImageData.from_frames([_star_field((0, 0)), _star_field((5, -3))])
        with self.assertRaises(PipelineError):
            build_reproject(build_wcs(), build_warp("nearest")).run(img)

    def test_wcs_registration_aligns_with_wcs(self) -> None:
        def mkwcs(crpix):
            w = WCS(naxis=2)
            w.wcs.ctype = ["RA---TAN", "DEC--TAN"]
            w.wcs.crpix = crpix
            w.wcs.crval = [10.0, 20.0]
            w.wcs.cdelt = [-1e-3, 1e-3]
            return w

        # Reference and a frame whose WCS encodes the same (5, -3) pixel offset.
        ref = _star_field((0, 0), wcs=mkwcs([32, 32]))
        moved = _star_field((5, -3), wcs=mkwcs([32 - 3, 32 + 5]))
        img = ImageData.from_frames([ref, moved])
        out = build_reproject(build_wcs(), build_warp("bilinear")).run(img)
        self.assertLess(_misalignment(out.lights["R"]), _misalignment(img.lights["R"]) * 0.5)


class ReprojectSpecTests(unittest.TestCase):
    def test_spec_shape_and_schema(self) -> None:
        self.assertEqual(REPROJECT.name, "Reproject")
        self.assertEqual(
            [s.name for s in REPROJECT.subprocesses], ["registration", "alignment"]
        )
        reg_algos = [a.name for a in REGISTRATION.algorithms]
        self.assertEqual(reg_algos, ["none", "astroalign", "phase_correlation", "wcs"])
        align_algos = [a.name for a in ALIGNMENT.algorithms]
        self.assertEqual(align_algos, ["bilinear", "nearest", "bicubic"])

    def test_spec_builds_and_runs(self) -> None:
        img = ImageData.from_frames([_star_field((0, 0)), _star_field((5, -3))])
        proc = REPROJECT.build(
            {
                "registration": {"algorithm": "astroalign", "params": {}},
                "alignment": {"algorithm": "bilinear", "params": {}},
            }
        )
        out = proc.run(img)
        self.assertLess(_misalignment(out.lights["R"]), _misalignment(img.lights["R"]) * 0.5)

    def test_spec_defaults_runnable(self) -> None:
        # Defaults: registration "none" + alignment "bilinear" -> a no-op-ish run.
        img = ImageData.from_frames([_star_field((0, 0)), _star_field((0, 0))])
        out = REPROJECT.build().run(img)
        self.assertEqual(set(out.filters), {"R"})


if __name__ == "__main__":
    unittest.main()
