import unittest
from unittest.mock import Mock, patch, mock_open, create_autospec
from pathlib import Path
import json

from playwright.sync_api import Page, CDPSession

from stwebagentbench.browser_env import StateInfo
from stwebagentbench.browser_env.custom_env import ActionTrace
from stwebagentbench.evaluation_harness.helper_functions import PseudoPage
from stwebagentbench.evaluation_harness import URLEvaluator


class TestURLEvaluator(unittest.TestCase):

    def setUp(self):
        self.evaluator = URLEvaluator()

    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "eval": {
            "eval_types": ["url_match"],
            "reference_url": "http://example.com/projects/1/issues",
            "url_note": "GOLD in PRED",
        }
    }))
    def test_url_match_success(self, mock_file):
        """URL match should return 1.0 when the page URL matches the reference."""
        action = {"action_type": "navigate"}
        state = StateInfo(info={}, observation={})
        trace = ActionTrace(action=action, state=state)

        trajectory = [trace]
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(Page, instance=True)
        page.url = "http://example.com/projects/1/issues"
        client = create_autospec(CDPSession, instance=True)

        result = self.evaluator(trajectory, config_file, page, client)

        self.assertAlmostEqual(result, 1.0)

    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "eval": {
            "eval_types": ["url_match"],
            "reference_url": "http://example.com/projects/1/issues",
            "url_note": "GOLD in PRED",
        }
    }))
    def test_url_match_failure(self, mock_file):
        """URL match should return 0.0 when the page URL does not match."""
        action = {"action_type": "navigate"}
        state = StateInfo(info={}, observation={})
        trace = ActionTrace(action=action, state=state)

        trajectory = [trace]
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(Page, instance=True)
        page.url = "http://example.com/projects/2/merge_requests"
        client = create_autospec(CDPSession, instance=True)

        result = self.evaluator(trajectory, config_file, page, client)

        self.assertAlmostEqual(result, 0.0)

    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "eval": {
            "eval_types": ["url_match"],
            "reference_url": "http://example.com/projects/1/issues |OR| http://example.com/projects/1/boards",
            "url_note": "GOLD in PRED",
        }
    }))
    def test_url_match_with_or_logic(self, mock_file):
        """URL match with OR logic should return 1.0 if any reference URL matches."""
        action = {"action_type": "navigate"}
        state = StateInfo(info={}, observation={})
        trace = ActionTrace(action=action, state=state)

        trajectory = [trace]
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(Page, instance=True)
        page.url = "http://example.com/projects/1/boards"
        client = create_autospec(CDPSession, instance=True)

        result = self.evaluator(trajectory, config_file, page, client)

        self.assertAlmostEqual(result, 1.0)


class TestURLEvaluatorQueryParams(unittest.TestCase):
    """Query parameter matching in URL evaluation."""

    def setUp(self):
        self.evaluator = URLEvaluator()

    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "eval": {
            "eval_types": ["url_match"],
            "reference_url": "http://example.com/search?q=test",
            "url_note": "GOLD in PRED",
        }
    }))
    def test_query_param_matches(self, mock_file):
        """URL with matching query param → 1.0."""
        action = {"action_type": "navigate"}
        state = StateInfo(info={}, observation={})
        trace = ActionTrace(action=action, state=state)
        page = create_autospec(Page, instance=True)
        page.url = "http://example.com/search?q=test&page=1"
        client = create_autospec(CDPSession, instance=True)
        result = self.evaluator([trace], Path("f.json"), page, client)
        self.assertAlmostEqual(result, 1.0)

    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "eval": {
            "eval_types": ["url_match"],
            "reference_url": "http://example.com/search?q=test",
            "url_note": "GOLD in PRED",
        }
    }))
    def test_wrong_query_param_fails(self, mock_file):
        """URL with different query param value → 0.0."""
        action = {"action_type": "navigate"}
        state = StateInfo(info={}, observation={})
        trace = ActionTrace(action=action, state=state)
        page = create_autospec(Page, instance=True)
        page.url = "http://example.com/search?q=other"
        client = create_autospec(CDPSession, instance=True)
        result = self.evaluator([trace], Path("f.json"), page, client)
        self.assertAlmostEqual(result, 0.0)

    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "eval": {
            "eval_types": ["url_match"],
            "reference_url": "http://example.com/projects/1/issues/",
            "url_note": "GOLD in PRED",
        }
    }))
    def test_trailing_slash_handling(self, mock_file):
        """Trailing slash in reference should still match."""
        action = {"action_type": "navigate"}
        state = StateInfo(info={}, observation={})
        trace = ActionTrace(action=action, state=state)
        page = create_autospec(Page, instance=True)
        page.url = "http://example.com/projects/1/issues"
        client = create_autospec(CDPSession, instance=True)
        result = self.evaluator([trace], Path("f.json"), page, client)
        self.assertAlmostEqual(result, 1.0)

    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "eval": {
            "eval_types": ["url_match"],
            "reference_url": "http://example.com/search?q=hello%20world",
            "url_note": "GOLD in PRED",
        }
    }))
    def test_percent_encoded_query(self, mock_file):
        """Percent-encoded query param should match."""
        action = {"action_type": "navigate"}
        state = StateInfo(info={}, observation={})
        trace = ActionTrace(action=action, state=state)
        page = create_autospec(Page, instance=True)
        page.url = "http://example.com/search?q=hello%20world"
        client = create_autospec(CDPSession, instance=True)
        result = self.evaluator([trace], Path("f.json"), page, client)
        self.assertAlmostEqual(result, 1.0)


if __name__ == '__main__':
    unittest.main()
