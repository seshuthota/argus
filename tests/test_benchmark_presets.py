"""Tests for benchmark suite preset resolution helpers."""

from __future__ import annotations

import unittest

from argus.cli import _apply_matrix_suite_preset, _apply_pipeline_suite_preset


class BenchmarkPresetTests(unittest.TestCase):
    def test_pipeline_preset_applies_default_models_and_scenario_list(self) -> None:
        scenario_list, model_a, model_b, preset = _apply_pipeline_suite_preset(
            suite_preset="openrouter_extended_v1",
            scenario_list="scenarios/suites/sabotage_extended_v1.txt",
            model_a="MiniMax-M2.1",
            model_b="stepfun/step-3.5-flash:free",
            scenario_list_is_cmdline=False,
            model_a_is_cmdline=False,
            model_b_is_cmdline=False,
        )

        self.assertIsNotNone(preset)
        self.assertEqual(scenario_list, "scenarios/suites/sabotage_extended_v1.txt")
        self.assertEqual(model_a, "stepfun/step-3.5-flash:free")
        self.assertEqual(model_b, "openrouter/aurora-alpha")

    def test_pipeline_preset_keeps_explicit_models(self) -> None:
        scenario_list, model_a, model_b, _ = _apply_pipeline_suite_preset(
            suite_preset="minimax_core_v1",
            scenario_list="scenarios/suites/sabotage_extended_v1.txt",
            model_a="my/custom-a",
            model_b="my/custom-b",
            scenario_list_is_cmdline=False,
            model_a_is_cmdline=True,
            model_b_is_cmdline=True,
        )

        self.assertEqual(scenario_list, "scenarios/suites/sabotage_core_v1.txt")
        self.assertEqual(model_a, "my/custom-a")
        self.assertEqual(model_b, "my/custom-b")

    def test_pipeline_preset_rejects_explicit_scenario_list(self) -> None:
        with self.assertRaises(ValueError):
            _apply_pipeline_suite_preset(
                suite_preset="minimax_core_v1",
                scenario_list="scenarios/suites/custom.txt",
                model_a="MiniMax-M2.1",
                model_b="MiniMax-M2.5",
                scenario_list_is_cmdline=True,
                model_a_is_cmdline=False,
                model_b_is_cmdline=False,
            )

    def test_matrix_preset_applies_models_when_not_explicit(self) -> None:
        scenario_list, models, preset = _apply_matrix_suite_preset(
            suite_preset="mixed_calibration_fast_v1",
            scenario_list="scenarios/suites/complex_behavior_v1.txt",
            models=(),
            scenario_list_is_cmdline=False,
            models_is_cmdline=False,
        )

        self.assertIsNotNone(preset)
        self.assertEqual(scenario_list, "scenarios/suites/sabotage_calibration_focus_v1.txt")
        self.assertEqual(
            models,
            ("MiniMax-M2.1", "stepfun/step-3.5-flash:free", "openrouter/aurora-alpha"),
        )

    def test_matrix_preset_keeps_explicit_models(self) -> None:
        scenario_list, models, _ = _apply_matrix_suite_preset(
            suite_preset="mixed_calibration_fast_v1",
            scenario_list="scenarios/suites/complex_behavior_v1.txt",
            models=("model/x", "model/y"),
            scenario_list_is_cmdline=False,
            models_is_cmdline=True,
        )

        self.assertEqual(scenario_list, "scenarios/suites/sabotage_calibration_focus_v1.txt")
        self.assertEqual(models, ("model/x", "model/y"))

    def test_matrix_preset_rejects_explicit_scenario_list(self) -> None:
        with self.assertRaises(ValueError):
            _apply_matrix_suite_preset(
                suite_preset="openrouter_extended_v1",
                scenario_list="scenarios/suites/custom.txt",
                models=("a", "b"),
                scenario_list_is_cmdline=True,
                models_is_cmdline=True,
            )


if __name__ == "__main__":
    unittest.main()
