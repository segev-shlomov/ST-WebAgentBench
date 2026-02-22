"""Tests for HTMLContentEvaluator — currently has ZERO test coverage.

HTMLContentEvaluator is a task evaluator (returns float, not Tuple).
It navigates to URLs, selects elements via locators, and evaluates
required_contents against the selected element text.

When locator="" the evaluator calls page.content() which returns the page HTML.
We use create_autospec(Page) to satisfy beartype and set content.return_value.
"""

import unittest
from unittest.mock import patch, mock_open, create_autospec
from pathlib import Path
import json

from playwright.sync_api import Page, CDPSession

from stwebagentbench.browser_env import StateInfo
from stwebagentbench.browser_env.custom_env import ActionTrace
from stwebagentbench.evaluation_harness import HTMLContentEvaluator


def _make_trace(action_type="click", action_args=None):
    action = {"action_type": action_type, "action_args": action_args or []}
    state = StateInfo(info={}, observation={})
    return ActionTrace(action=action, state=state)


def _create_mock_page(url="http://example.com", html_content=""):
    """Create a beartype-compatible Page mock where content() returns a string."""
    page = create_autospec(Page, instance=True)
    page.url = url
    page.content.return_value = html_content
    return page


class TestHTMLContentEvaluatorMustInclude(unittest.TestCase):
    """Test must_include in required_contents."""

    def setUp(self):
        self.evaluator = HTMLContentEvaluator()
        self.client = create_autospec(CDPSession, instance=True)

    @patch("time.sleep")
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "eval": {
            "eval_types": ["program_html"],
            "program_html": [{
                "url": "last",
                "locator": "",
                "required_contents": {
                    "must_include": ["Order Confirmed"]
                }
            }]
        }
    }))
    def test_must_include_success(self, mock_file, _sleep):
        """Content present in page HTML → 1.0."""
        page = _create_mock_page(html_content="<html>Your Order Confirmed Successfully</html>")
        trajectory = [_make_trace()]
        result = self.evaluator(trajectory, Path("f.json"), page, self.client)
        self.assertAlmostEqual(result, 1.0)

    @patch("time.sleep")
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "eval": {
            "eval_types": ["program_html"],
            "program_html": [{
                "url": "last",
                "locator": "",
                "required_contents": {
                    "must_include": ["Order Confirmed"]
                }
            }]
        }
    }))
    def test_must_include_failure(self, mock_file, _sleep):
        """Content NOT in page HTML → 0.0."""
        page = _create_mock_page(html_content="<html>Shopping Cart Empty</html>")
        trajectory = [_make_trace()]
        result = self.evaluator(trajectory, Path("f.json"), page, self.client)
        self.assertAlmostEqual(result, 0.0)


class TestHTMLContentEvaluatorExactMatch(unittest.TestCase):
    """Test exact_match in required_contents."""

    def setUp(self):
        self.evaluator = HTMLContentEvaluator()
        self.client = create_autospec(CDPSession, instance=True)

    @patch("time.sleep")
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "eval": {
            "eval_types": ["program_html"],
            "program_html": [{
                "url": "last",
                "locator": "",
                "required_contents": {
                    "exact_match": "$99.99"
                }
            }]
        }
    }))
    def test_exact_match_success(self, mock_file, _sleep):
        """Exact match of page content → 1.0."""
        page = _create_mock_page(html_content="$99.99")
        trajectory = [_make_trace()]
        result = self.evaluator(trajectory, Path("f.json"), page, self.client)
        self.assertAlmostEqual(result, 1.0)

    @patch("time.sleep")
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "eval": {
            "eval_types": ["program_html"],
            "program_html": [{
                "url": "last",
                "locator": "",
                "required_contents": {
                    "exact_match": "$99.99"
                }
            }]
        }
    }))
    def test_exact_match_failure(self, mock_file, _sleep):
        """Different text → 0.0."""
        page = _create_mock_page(html_content="$49.99")
        trajectory = [_make_trace()]
        result = self.evaluator(trajectory, Path("f.json"), page, self.client)
        self.assertAlmostEqual(result, 0.0)


class TestHTMLContentEvaluatorNotEmpty(unittest.TestCase):
    """Test not_empty in required_contents."""

    def setUp(self):
        self.evaluator = HTMLContentEvaluator()
        self.client = create_autospec(CDPSession, instance=True)

    @patch("time.sleep")
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "eval": {
            "eval_types": ["program_html"],
            "program_html": [{
                "url": "last",
                "locator": "",
                "required_contents": {
                    "not_empty": ""
                }
            }]
        }
    }))
    def test_not_empty_passes_with_content(self, mock_file, _sleep):
        """Page has content → 1.0."""
        page = _create_mock_page(html_content="<html>Some content</html>")
        trajectory = [_make_trace()]
        result = self.evaluator(trajectory, Path("f.json"), page, self.client)
        self.assertAlmostEqual(result, 1.0)

    @patch("time.sleep")
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "eval": {
            "eval_types": ["program_html"],
            "program_html": [{
                "url": "last",
                "locator": "",
                "required_contents": {
                    "not_empty": ""
                }
            }]
        }
    }))
    def test_not_empty_fails_with_empty(self, mock_file, _sleep):
        """Empty page → 0.0."""
        page = _create_mock_page(html_content="")
        trajectory = [_make_trace()]
        result = self.evaluator(trajectory, Path("f.json"), page, self.client)
        self.assertAlmostEqual(result, 0.0)


class TestHTMLContentEvaluatorMultipleTargets(unittest.TestCase):
    """Multiple program_html targets — all must pass for score=1.0."""

    def setUp(self):
        self.evaluator = HTMLContentEvaluator()
        self.client = create_autospec(CDPSession, instance=True)

    @patch("time.sleep")
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "eval": {
            "eval_types": ["program_html"],
            "program_html": [
                {
                    "url": "last",
                    "locator": "",
                    "required_contents": {
                        "must_include": ["Product A"]
                    }
                },
                {
                    "url": "last",
                    "locator": "",
                    "required_contents": {
                        "must_include": ["In Stock"]
                    }
                }
            ]
        }
    }))
    def test_all_targets_pass(self, mock_file, _sleep):
        """Both targets satisfied → 1.0."""
        page = _create_mock_page(html_content="Product A - In Stock - $19.99")
        trajectory = [_make_trace()]
        result = self.evaluator(trajectory, Path("f.json"), page, self.client)
        self.assertAlmostEqual(result, 1.0)

    @patch("time.sleep")
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "eval": {
            "eval_types": ["program_html"],
            "program_html": [
                {
                    "url": "last",
                    "locator": "",
                    "required_contents": {
                        "must_include": ["Product A"]
                    }
                },
                {
                    "url": "last",
                    "locator": "",
                    "required_contents": {
                        "must_include": ["Out of Stock"]
                    }
                }
            ]
        }
    }))
    def test_one_target_fails(self, mock_file, _sleep):
        """Second target fails → 0.0 (score multiplied)."""
        page = _create_mock_page(html_content="Product A - In Stock")
        trajectory = [_make_trace()]
        result = self.evaluator(trajectory, Path("f.json"), page, self.client)
        self.assertAlmostEqual(result, 0.0)


class TestHTMLContentEvaluatorORLogic(unittest.TestCase):
    """Test |OR| logic in must_include values."""

    def setUp(self):
        self.evaluator = HTMLContentEvaluator()
        self.client = create_autospec(CDPSession, instance=True)

    @patch("time.sleep")
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "eval": {
            "eval_types": ["program_html"],
            "program_html": [{
                "url": "last",
                "locator": "",
                "required_contents": {
                    "must_include": ["shipped |OR| delivered"]
                }
            }]
        }
    }))
    def test_or_first_alternative(self, mock_file, _sleep):
        """First OR alternative matches → 1.0."""
        page = _create_mock_page(html_content="Your order has been shipped")
        trajectory = [_make_trace()]
        result = self.evaluator(trajectory, Path("f.json"), page, self.client)
        self.assertAlmostEqual(result, 1.0)

    @patch("time.sleep")
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "eval": {
            "eval_types": ["program_html"],
            "program_html": [{
                "url": "last",
                "locator": "",
                "required_contents": {
                    "must_include": ["shipped |OR| delivered"]
                }
            }]
        }
    }))
    def test_or_second_alternative(self, mock_file, _sleep):
        """Second OR alternative matches → 1.0."""
        page = _create_mock_page(html_content="Package delivered")
        trajectory = [_make_trace()]
        result = self.evaluator(trajectory, Path("f.json"), page, self.client)
        self.assertAlmostEqual(result, 1.0)

    @patch("time.sleep")
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "eval": {
            "eval_types": ["program_html"],
            "program_html": [{
                "url": "last",
                "locator": "",
                "required_contents": {
                    "must_include": ["shipped |OR| delivered"]
                }
            }]
        }
    }))
    def test_or_neither_matches(self, mock_file, _sleep):
        """Neither OR alternative matches → 0.0."""
        page = _create_mock_page(html_content="Order is processing")
        trajectory = [_make_trace()]
        result = self.evaluator(trajectory, Path("f.json"), page, self.client)
        self.assertAlmostEqual(result, 0.0)


if __name__ == "__main__":
    unittest.main()
