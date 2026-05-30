"""Tests for the typed parameter descriptors (validation + JSON schema)."""
from __future__ import annotations

import json
import unittest

from pmo_stacklab.modules.core import BoolParam, ChoiceParam, FloatParam, IntParam


class FloatParamTests(unittest.TestCase):
    def test_coerces_and_bounds_checks(self) -> None:
        p = FloatParam(name="sigma", default=3.0, minimum=0.0, maximum=10.0)
        self.assertEqual(p.validate("2.5"), 2.5)  # coerced from string
        self.assertEqual(p.validate(4), 4.0)
        with self.assertRaises(ValueError):
            p.validate(-1.0)
        with self.assertRaises(ValueError):
            p.validate(11.0)
        with self.assertRaises(ValueError):
            p.validate("not a number")

    def test_to_dict_is_json_serializable(self) -> None:
        p = FloatParam(
            name="sigma", default=3.0, minimum=0.0, maximum=10.0, step=0.5, description="clip"
        )
        d = p.to_dict()
        self.assertEqual(d["type"], "float")
        self.assertEqual(d["default"], 3.0)
        self.assertEqual(d["minimum"], 0.0)
        json.dumps(d)


class IntParamTests(unittest.TestCase):
    def test_rejects_non_integral_and_bounds(self) -> None:
        p = IntParam(name="n", default=1, minimum=1)
        self.assertEqual(p.validate(3), 3)
        self.assertEqual(p.validate("4"), 4)
        self.assertEqual(p.validate(5.0), 5)  # integral float accepted
        with self.assertRaises(ValueError):
            p.validate(2.5)  # non-integral float rejected
        with self.assertRaises(ValueError):
            p.validate(0)  # below minimum


class BoolParamTests(unittest.TestCase):
    def test_accepts_common_forms(self) -> None:
        p = BoolParam(name="scale", default=True)
        self.assertIs(p.validate(False), False)
        self.assertIs(p.validate("true"), True)
        self.assertIs(p.validate("false"), False)
        with self.assertRaises(ValueError):
            p.validate("maybe")


class ChoiceParamTests(unittest.TestCase):
    def test_validates_membership(self) -> None:
        p = ChoiceParam(name="kind", choices=("nearest", "bilinear"), default="bilinear")
        self.assertEqual(p.validate("nearest"), "nearest")
        with self.assertRaises(ValueError):
            p.validate("bicubic")

    def test_default_must_be_a_choice(self) -> None:
        with self.assertRaises(ValueError):
            ChoiceParam(name="kind", choices=("a", "b"), default="z")

    def test_to_dict_is_json_serializable(self) -> None:
        d = ChoiceParam(name="kind", choices=("a", "b"), default="a").to_dict()
        self.assertEqual(d["type"], "choice")
        self.assertEqual(d["choices"], ["a", "b"])
        json.dumps(d)


if __name__ == "__main__":
    unittest.main()
