"""Tests for the generalized algorithm builder (Algorithm + Subprocess registry).

These tests deliberately use *synthetic* algorithms whose builders return values
of varied shapes, to prove the registry is agnostic to what an algorithm produces
-- the property that lets the same machinery serve Stack, Calibrate, Reproject,
and Post-Process alike.
"""
from __future__ import annotations

import json
import unittest

from pmo_stacklab.modules.core import Algorithm, ChoiceParam, FloatParam, Subprocess


class AlgorithmBuildTests(unittest.TestCase):
    def test_builder_return_type_is_unconstrained(self) -> None:
        # A builder may return a callable of any shape...
        scale = Algorithm(
            name="scale",
            builder=lambda factor: (lambda x: x * factor),
            parameters=(FloatParam(name="factor", default=2.0),),
        )
        configured = scale.build({"factor": 3.0})
        self.assertEqual(configured(10), 30)

        # ...or a value that is not callable at all; the registry does not care.
        constant = Algorithm(name="constant", builder=lambda: "not callable")
        self.assertEqual(constant.build(), "not callable")

    def test_missing_param_uses_default(self) -> None:
        algo = Algorithm(
            name="k", builder=lambda k: k, parameters=(FloatParam(name="k", default=7.0),)
        )
        self.assertEqual(algo.build({}), 7.0)
        self.assertEqual(algo.build(None), 7.0)

    def test_params_are_validated_before_building(self) -> None:
        algo = Algorithm(
            name="s",
            builder=lambda s: s,
            parameters=(FloatParam(name="s", default=1.0, minimum=0.0, maximum=5.0),),
        )
        self.assertEqual(algo.build({"s": "2.5"}), 2.5)  # coerced
        with self.assertRaises(ValueError):
            algo.build({"s": 99.0})  # out of range

    def test_unknown_keys_are_ignored(self) -> None:
        algo = Algorithm(
            name="k", builder=lambda k: k, parameters=(FloatParam(name="k", default=1.0),)
        )
        self.assertEqual(algo.build({"k": 2.0, "ignored": "x"}), 2.0)


class SubprocessTests(unittest.TestCase):
    @staticmethod
    def _subprocess() -> Subprocess:
        return Subprocess(
            name="rejection",
            label="Outlier Rejection",
            algorithms=(
                Algorithm(name="none", builder=lambda: "noop", label="None"),
                Algorithm(
                    name="sigma_clip",
                    label="Sigma Clip",
                    builder=lambda sigma, stdfunc: (sigma, stdfunc),
                    parameters=(
                        FloatParam(name="sigma", default=3.0, minimum=0.0, maximum=10.0),
                        ChoiceParam(
                            name="stdfunc", choices=("std", "mad_std"), default="mad_std"
                        ),
                    ),
                ),
            ),
        )

    def test_builds_chosen_algorithm(self) -> None:
        sub = self._subprocess()
        self.assertEqual(sub.build("sigma_clip", {"sigma": 2.5}), (2.5, "mad_std"))
        self.assertEqual(sub.build("none"), "noop")

    def test_unknown_algorithm_raises(self) -> None:
        with self.assertRaises(KeyError):
            self._subprocess().build("does_not_exist")

    def test_schema_is_json_serializable(self) -> None:
        schema = self._subprocess().to_dict()
        self.assertEqual(schema["name"], "rejection")
        self.assertEqual(schema["label"], "Outlier Rejection")
        sigma_algo = schema["algorithms"][1]
        self.assertEqual(
            [p["type"] for p in sigma_algo["parameters"]], ["float", "choice"]
        )
        json.dumps(schema)  # the whole schema must round-trip to JSON


if __name__ == "__main__":
    unittest.main()
