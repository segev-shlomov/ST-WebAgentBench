"""Tests for unified error handling (Phase 3).

Covers:
- _handle_eval_error in lenient mode returns dormant report
- _handle_eval_error in strict mode raises EvaluationError
- CountActionEvaluator uses graceful error handling for missing params
- RapidFuzz fallback in GeneralErrorEvaluator
"""

import unittest
from unittest.mock import patch, mock_open, create_autospec
from pathlib import Path

from playwright.sync_api import CDPSession

from stwebagentbench.browser_env import StateInfo
from stwebagentbench.browser_env.custom_env import ActionTrace
from stwebagentbench.evaluation_harness.helper_functions import PseudoPage
from stwebagentbench.evaluation_harness.evaluators import (
    _handle_eval_error,
    EvaluationError,
    EVALUATION_ERROR_MODE,
    CountActionEvaluator,
    GeneralErrorEvaluator,
    create_report_point,
)
import stwebagentbench.evaluation_harness.evaluators as evaluators_module


def _make_trace(action_type, action_args=None, element_text="", element_bid=""):
    action = {"action_type": action_type, "action_args": action_args or []}
    state = StateInfo(
        info={"element_text": element_text, "element_bid": element_bid},
        observation={},
    )
    return ActionTrace(action=action, state=state)


class TestHandleEvalErrorLenient(unittest.TestCase):
    """Default (lenient) mode: log + return dormant report."""

    def test_returns_dormant_report(self):
        params = {"policy_template_id": "test_policy"}
        score, report = _handle_eval_error(
            "TestEvaluator", ValueError("boom"), params, "something broke"
        )
        self.assertEqual(score, 0.0)
        self.assertFalse(report["violated"])
        self.assertTrue(report["dormant"])
        self.assertEqual(report["confidence"], "error_degraded")

    def test_returns_eval_type_in_report(self):
        params = {"policy_template_id": "test"}
        _, report = _handle_eval_error(
            "MyEval", RuntimeError("x"), params, "msg"
        )
        self.assertEqual(report["eval_type"], "MyEval")


class TestHandleEvalErrorStrict(unittest.TestCase):
    """Strict mode: raises EvaluationError."""

    def setUp(self):
        self._original_mode = evaluators_module.EVALUATION_ERROR_MODE

    def tearDown(self):
        evaluators_module.EVALUATION_ERROR_MODE = self._original_mode

    def test_raises_evaluation_error(self):
        evaluators_module.EVALUATION_ERROR_MODE = "strict"
        params = {"policy_template_id": "test_policy"}
        with self.assertRaises(EvaluationError) as ctx:
            _handle_eval_error("TestEval", ValueError("boom"), params, "something broke")
        self.assertIn("test_policy", str(ctx.exception))
        self.assertIn("something broke", str(ctx.exception))


class TestCountActionEvaluatorErrorHandling(unittest.TestCase):
    """CountActionEvaluator uses _handle_eval_error for missing required params."""

    def setUp(self):
        self.config_file = Path("test_eval/fake_config.json")
        self.page = create_autospec(PseudoPage, instance=True)
        self.page.url = "http://example.com"
        self.client = create_autospec(CDPSession, instance=True)

    @patch("builtins.open", new_callable=mock_open, read_data="{}")
    def test_missing_action_type_returns_dormant(self, _):
        """Missing action_type → graceful degradation, not ValueError."""
        params = {
            "policy_template_id": "test",
            "eval": {
                "eval_types": ["is_action_count"],
                "action_type": "",
                "global_count": 0,
            },
        }
        evaluator = CountActionEvaluator(params=params)
        trajectory = [_make_trace("click")]
        score, report = evaluator(trajectory, self.config_file, self.page, self.client)
        self.assertEqual(score, 0.0)
        self.assertTrue(report.get("dormant", False))
        self.assertEqual(report.get("confidence"), "error_degraded")

    @patch("builtins.open", new_callable=mock_open, read_data="{}")
    def test_missing_count_params_returns_dormant(self, _):
        """Missing both global_count and global_count_less_than → graceful degradation."""
        params = {
            "policy_template_id": "test",
            "eval": {
                "eval_types": ["is_action_count"],
                "action_type": "click",
            },
        }
        evaluator = CountActionEvaluator(params=params)
        trajectory = [_make_trace("click")]
        score, report = evaluator(trajectory, self.config_file, self.page, self.client)
        self.assertEqual(score, 0.0)
        self.assertTrue(report.get("dormant", False))

    @patch("builtins.open", new_callable=mock_open, read_data="{}")
    def test_missing_action_type_strict_raises(self, _):
        """In strict mode, missing action_type raises EvaluationError."""
        original = evaluators_module.EVALUATION_ERROR_MODE
        try:
            evaluators_module.EVALUATION_ERROR_MODE = "strict"
            params = {
                "policy_template_id": "test",
                "eval": {
                    "eval_types": ["is_action_count"],
                    "action_type": "",
                    "global_count": 0,
                },
            }
            evaluator = CountActionEvaluator(params=params)
            trajectory = [_make_trace("click")]
            with self.assertRaises(EvaluationError):
                evaluator(trajectory, self.config_file, self.page, self.client)
        finally:
            evaluators_module.EVALUATION_ERROR_MODE = original


class TestGeneralErrorRapidFuzzFallback(unittest.TestCase):
    """GeneralErrorEvaluator falls back to substring matching without RapidFuzz."""

    def setUp(self):
        self.config_file = Path("test_eval/fake_config.json")
        self.client = create_autospec(CDPSession, instance=True)

    @patch("builtins.open", new_callable=mock_open, read_data="{}")
    def test_fallback_substring_match_passes(self, _):
        """When rapidfuzz is unavailable, exact substring match should still pass."""
        params = {
            "policy_template_id": "popup_error",
            "description": "handle 404 error",
            "eval": {"eval_types": ["popup_error"]},
        }
        from playwright.sync_api import Page
        # Use create_autospec(Page) for beartype compatibility
        # Page has inner_text, so evaluator uses page.inner_text('body')
        page = create_autospec(Page, instance=True)
        page.url = "http://example.com/missing"
        page.inner_text.return_value = "404 not found"

        evaluator = GeneralErrorEvaluator(params=params)
        trajectory = [
            _make_trace("send_msg_to_user", action_args=["handle 404 error please"]),
        ]

        # Patch rapidfuzz import to fail, forcing fallback
        import builtins
        original_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "rapidfuzz":
                raise ImportError("no rapidfuzz")
            return original_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            score, report = evaluator(trajectory, self.config_file, page, self.client)

        self.assertEqual(score, 0.0)
        self.assertFalse(report["violated"])


if __name__ == "__main__":
    unittest.main()
