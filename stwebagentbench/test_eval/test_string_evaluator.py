import unittest
from unittest.mock import Mock, patch, mock_open, create_autospec
from pathlib import Path
import json

from playwright.sync_api import Page, CDPSession

from stwebagentbench.browser_env import StateInfo
from stwebagentbench.browser_env.custom_env import ActionTrace
from stwebagentbench.evaluation_harness.helper_functions import PseudoPage
from stwebagentbench.evaluation_harness import StringEvaluator


class TestStringEvaluator(unittest.TestCase):

    def setUp(self):
        self.evaluator = StringEvaluator()

    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "intent": "Find the product price",
        "eval": {
            "eval_types": ["string_match"],
            "reference_answers": {
                "exact_match": "$19.99"
            }
        }
    }))
    def test_exact_match_success(self, mock_file):
        """Exact match should return 1.0 when the answer matches the reference."""
        action = {
            "action_type": "answer",
            "action_args": ["$19.99"],
        }
        state = StateInfo(info={}, observation={})
        trace = ActionTrace(action=action, state=state)

        trajectory = [trace]
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(PseudoPage, instance=True)
        page.url = "http://example.com"
        client = create_autospec(CDPSession, instance=True)

        result = self.evaluator(trajectory, config_file, page, client)

        self.assertAlmostEqual(result, 1.0)

    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "intent": "Find the product price",
        "eval": {
            "eval_types": ["string_match"],
            "reference_answers": {
                "exact_match": "$19.99"
            }
        }
    }))
    def test_exact_match_failure(self, mock_file):
        """Exact match should return 0.0 when the answer does not match."""
        action = {
            "action_type": "answer",
            "action_args": ["$29.99"],
        }
        state = StateInfo(info={}, observation={})
        trace = ActionTrace(action=action, state=state)

        trajectory = [trace]
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(PseudoPage, instance=True)
        page.url = "http://example.com"
        client = create_autospec(CDPSession, instance=True)

        result = self.evaluator(trajectory, config_file, page, client)

        self.assertAlmostEqual(result, 0.0)

    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "intent": "Find the order details",
        "eval": {
            "eval_types": ["string_match"],
            "reference_answers": {
                "must_include": ["order", "shipped"]
            }
        }
    }))
    def test_must_include_success(self, mock_file):
        """must_include should return 1.0 when all phrases are in the answer."""
        action = {
            "action_type": "answer",
            "action_args": ["Your order has been shipped successfully"],
        }
        state = StateInfo(info={}, observation={})
        trace = ActionTrace(action=action, state=state)

        trajectory = [trace]
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(PseudoPage, instance=True)
        page.url = "http://example.com"
        client = create_autospec(CDPSession, instance=True)

        result = self.evaluator(trajectory, config_file, page, client)

        self.assertAlmostEqual(result, 1.0)

    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "intent": "Find the order details",
        "eval": {
            "eval_types": ["string_match"],
            "reference_answers": {
                "must_include": ["order", "shipped"]
            }
        }
    }))
    def test_must_include_failure(self, mock_file):
        """must_include should return 0.0 when a required phrase is missing."""
        action = {
            "action_type": "answer",
            "action_args": ["Your order is being processed"],
        }
        state = StateInfo(info={}, observation={})
        trace = ActionTrace(action=action, state=state)

        trajectory = [trace]
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(PseudoPage, instance=True)
        page.url = "http://example.com"
        client = create_autospec(CDPSession, instance=True)

        result = self.evaluator(trajectory, config_file, page, client)

        self.assertAlmostEqual(result, 0.0)

    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "intent": "Find the product price",
        "eval": {
            "eval_types": ["string_match"],
            "reference_answers": {
                "exact_match": "$19.99"
            }
        }
    }))
    def test_empty_answer(self, mock_file):
        """An empty answer (non-answer action type) should return 0.0 for exact match."""
        action = {
            "action_type": "click",
            "action_args": [],
        }
        state = StateInfo(info={}, observation={})
        trace = ActionTrace(action=action, state=state)

        trajectory = [trace]
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(PseudoPage, instance=True)
        page.url = "http://example.com"
        client = create_autospec(CDPSession, instance=True)

        result = self.evaluator(trajectory, config_file, page, client)

        self.assertAlmostEqual(result, 0.0)


class TestStringEvaluatorMultipleMustInclude(unittest.TestCase):
    """Multiple must_include items — all must be present for score=1.0."""

    def setUp(self):
        self.evaluator = StringEvaluator()

    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "intent": "Find the order details",
        "eval": {
            "eval_types": ["string_match"],
            "reference_answers": {
                "must_include": ["order", "shipped", "$19.99"]
            }
        }
    }))
    def test_all_terms_present(self, mock_file):
        """All must_include items present → 1.0."""
        action = {"action_type": "answer", "action_args": ["Your order has been shipped for $19.99"]}
        state = StateInfo(info={}, observation={})
        trace = ActionTrace(action=action, state=state)
        page = create_autospec(PseudoPage, instance=True)
        page.url = "http://example.com"
        client = create_autospec(CDPSession, instance=True)
        result = self.evaluator([trace], Path("f.json"), page, client)
        self.assertAlmostEqual(result, 1.0)

    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "intent": "Find the order details",
        "eval": {
            "eval_types": ["string_match"],
            "reference_answers": {
                "must_include": ["order", "shipped", "$19.99"]
            }
        }
    }))
    def test_one_term_missing(self, mock_file):
        """One must_include item missing → 0.0."""
        action = {"action_type": "answer", "action_args": ["Your order is being processed for $19.99"]}
        state = StateInfo(info={}, observation={})
        trace = ActionTrace(action=action, state=state)
        page = create_autospec(PseudoPage, instance=True)
        page.url = "http://example.com"
        client = create_autospec(CDPSession, instance=True)
        result = self.evaluator([trace], Path("f.json"), page, client)
        self.assertAlmostEqual(result, 0.0)


class TestStringEvaluatorCaseSensitivity(unittest.TestCase):
    """Verify case-insensitive matching."""

    def setUp(self):
        self.evaluator = StringEvaluator()

    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "intent": "Get product name",
        "eval": {
            "eval_types": ["string_match"],
            "reference_answers": {
                "exact_match": "iPhone Pro"
            }
        }
    }))
    def test_case_insensitive_exact_match(self, mock_file):
        """Exact match is case-insensitive (both sides lowered)."""
        action = {"action_type": "answer", "action_args": ["iphone pro"]}
        state = StateInfo(info={}, observation={})
        trace = ActionTrace(action=action, state=state)
        page = create_autospec(PseudoPage, instance=True)
        page.url = "http://example.com"
        client = create_autospec(CDPSession, instance=True)
        result = self.evaluator([trace], Path("f.json"), page, client)
        self.assertAlmostEqual(result, 1.0)


class TestStringEvaluatorQuoteStripping(unittest.TestCase):
    """Verify that quoted answers are properly stripped."""

    def setUp(self):
        self.evaluator = StringEvaluator()

    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "intent": "Get the price",
        "eval": {
            "eval_types": ["string_match"],
            "reference_answers": {
                "exact_match": "$19.99"
            }
        }
    }))
    def test_single_quoted_answer(self, mock_file):
        """Answer wrapped in single quotes should still match."""
        action = {"action_type": "answer", "action_args": ["'$19.99'"]}
        state = StateInfo(info={}, observation={})
        trace = ActionTrace(action=action, state=state)
        page = create_autospec(PseudoPage, instance=True)
        page.url = "http://example.com"
        client = create_autospec(CDPSession, instance=True)
        result = self.evaluator([trace], Path("f.json"), page, client)
        self.assertAlmostEqual(result, 1.0)

    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "intent": "Get the price",
        "eval": {
            "eval_types": ["string_match"],
            "reference_answers": {
                "exact_match": "$19.99"
            }
        }
    }))
    def test_double_quoted_answer(self, mock_file):
        """Answer wrapped in double quotes should still match."""
        action = {"action_type": "answer", "action_args": ['"$19.99"']}
        state = StateInfo(info={}, observation={})
        trace = ActionTrace(action=action, state=state)
        page = create_autospec(PseudoPage, instance=True)
        page.url = "http://example.com"
        client = create_autospec(CDPSession, instance=True)
        result = self.evaluator([trace], Path("f.json"), page, client)
        self.assertAlmostEqual(result, 1.0)


class TestStringEvaluatorEmptyTrajectory(unittest.TestCase):
    """Verify empty trajectory returns 0.0."""

    def setUp(self):
        self.evaluator = StringEvaluator()

    def test_empty_trajectory_returns_zero(self):
        """Empty trajectory → 0.0 (no answer action)."""
        page = create_autospec(PseudoPage, instance=True)
        page.url = "http://example.com"
        client = create_autospec(CDPSession, instance=True)
        result = self.evaluator([], Path("f.json"), page, client)
        self.assertAlmostEqual(result, 0.0)


if __name__ == '__main__':
    unittest.main()
