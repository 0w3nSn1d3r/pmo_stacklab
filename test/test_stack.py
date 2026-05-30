"""Tests for the Stack process: coordinator composition and per-filter collapse."""
from __future__ import annotations

import unittest

import numpy as np
from astropy.nddata import CCDData

from pmo_stacklab.modules.core import ImageData
from pmo_stacklab.modules.stacking import Coaddition, build_stack, no_rejection
from pmo_stacklab.modules.stacking.stack import CubeOperator


def _light(filt: str, value: float) -> CCDData:
    """A small uniform light frame (all pixels == ``value``) under filter ``filt``."""
    return CCDData(
        np.full((3, 3), value, dtype=float), unit="adu", meta={"FILTER": filt}
    )


def _mean(cube: np.ndarray) -> np.ndarray:
    """A coaddition operator: masked mean across the frame axis."""
    return np.ma.mean(cube, axis=0)


def _mask_above(threshold: float) -> CubeOperator:
    """A rejection operator that masks pixels strictly greater than ``threshold``."""

    def outlier(cube: np.ndarray) -> np.ndarray:
        return np.ma.masked_greater(cube, threshold)

    return outlier


class StackProcessTests(unittest.TestCase):
    def test_collapses_to_one_frame_per_filter(self) -> None:
        img = ImageData.from_frames(
            [_light("R", 1.0), _light("R", 3.0), _light("G", 5.0)]
        )
        process = build_stack(no_rejection, _mean)
        out = process.run(img)

        self.assertEqual(process.name, "Stack")
        self.assertTrue(out.is_stacked)
        self.assertEqual(float(out.lights["R"][0].data.mean()), 2.0)  # mean(1, 3)
        self.assertEqual(float(out.lights["G"][0].data.mean()), 5.0)

    def test_rejection_runs_before_coaddition(self) -> None:
        img = ImageData.from_frames(
            [_light("R", 2.0), _light("R", 2.0), _light("R", 2.0), _light("R", 8.0)]
        )
        # Masking > 5 drops the 8 before the mean: mean(2, 2, 2) == 2.0 ...
        rejected = build_stack(_mask_above(5.0), _mean).run(img)
        self.assertEqual(float(rejected.lights["R"][0].data.mean()), 2.0)
        # ... whereas skipping rejection averages it in: mean(2, 2, 2, 8) == 3.5.
        kept = build_stack(no_rejection, _mean).run(img)
        self.assertEqual(float(kept.lights["R"][0].data.mean()), 3.5)

    def test_existing_coaddition_builder_conforms(self) -> None:
        # The package's existing Coaddition builder must satisfy the new contract.
        img = ImageData.from_frames(
            [_light("R", 1.0), _light("R", 3.0), _light("R", 11.0)]
        )
        out = build_stack(no_rejection, Coaddition.build_median()).run(img)
        self.assertEqual(float(out.lights["R"][0].data.mean()), 3.0)  # median(1, 3, 11)


if __name__ == "__main__":
    unittest.main()
