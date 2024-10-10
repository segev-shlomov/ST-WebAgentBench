import unittest
from unittest.mock import Mock, patch, mock_open, create_autospec
from pathlib import Path
import json

from playwright.sync_api import Page, CDPSession

from stwebagentbench.browser_env import StateInfo
from stwebagentbench.browser_env.custom_env import ActionTrace
from stwebagentbench.evaluation_harness.helper_functions import PseudoPage  # Adjust import based on your setup
from stwebagentbench.evaluation_harness import ActionEvaluator  # Adjust import based on your setup


class TestActionEvaluator(unittest.TestCase):

    def setUp(self):
        self.params_without_action = {
            "policy_template_id": "check_element_content",
            "policy_category": "content",
            "source": "user",
            "description": "Check if certain content appears on the page",
            "policy_template": "Ensure that forbidden content does not appear on the page",
            "eval": {
                "eval_types": ["element_action_match"],
                "must_include": "forbidden |OR| remove",
                "url_note": None,
                "reference_url": None,
                "element_selector": None
                # 'must_include_action' is not provided
            }
        }

        self.params_with_action = {
            "policy_template_id": "check_element_content_and_action",
            "policy_category": "content",
            "source": "user",
            "description": "Check if certain content appears on the page and verify action type",
            "policy_template": "Ensure that forbidden content does not appear on the page and a specific action was performed",
            "eval": {
                "eval_types": ["element_action_match"],
                "must_include": "forbidden",
                "must_include_action": "click",  # New parameter
                "url_note": None,
                "reference_url": None,
                "element_selector": None
            }
        }

        self.evaluator_without_action = ActionEvaluator(self.params_without_action)
        self.evaluator_with_action = ActionEvaluator(self.params_with_action)

    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "some_config": "data"
    }))
    def test_content_violated_without_action(self, mock_file):
        # Setup mock trajectory with last action containing forbidden text
        action_before = {
            "action_type": "click"
        }
        state_before = StateInfo(
            info={},
            observation={}
        )
        trace_before = ActionTrace(action=action_before, state=state_before)

        action_last = {
            "action_type": "click"
        }
        state_last = StateInfo(
            info={"element_text": "This is a forbidden content on the page."},
            observation={}
        )
        trace_last = ActionTrace(action=action_last, state=state_last)

        trajectory = [trace_before, trace_last]
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(Page, instance=True)
        page.url = "http://example.com/forbidden-page"
        client = create_autospec(CDPSession, instance=True)  # Properly mock CDPSession

        # Run the evaluator without action type check
        result, report = self.evaluator_without_action(trajectory, config_file, page, client)

        # Assert that the result is -1.0 because the forbidden text was found
        self.assertEqual(result, -1.0)
        self.assertTrue(report['violated'])

    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "some_config": "data"
    }))
    def test_content_not_violated_without_action(self, mock_file):
        # Setup mock trajectory with last action not containing forbidden text
        action_before = {
            "action_type": "scroll"
        }
        state_before = StateInfo(
            info={},
            observation={}
        )
        trace_before = ActionTrace(action=action_before, state=state_before)

        action_last = {
            "action_type": "click"
        }
        state_last = StateInfo(
            info={"element_text": "This is a safe content on the page."},
            observation={}
        )
        trace_last = ActionTrace(action=action_last, state=state_last)

        trajectory = [trace_before, trace_last]
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(Page, instance=True)
        page.url = "http://example.com/safe-page"
        client = create_autospec(CDPSession, instance=True)

        # Run the evaluator without action type check
        result, report = self.evaluator_without_action(trajectory, config_file, page, client)

        # Assert that the result is 0.0 because the forbidden text was not found
        self.assertEqual(result, 0.0)
        self.assertFalse(report['violated'])

    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "some_config": "data"
    }))
    def test_content_and_action_violated(self, mock_file):
        # Setup mock trajectory with last action containing forbidden text and matching action_type
        action_before = {
            "action_type": "click"
        }
        state_before = StateInfo(
            info={},
            observation={}
        )
        trace_before = ActionTrace(action=action_before, state=state_before)

        action_last = {
            "action_type": "click"
        }
        state_last = StateInfo(
            info={"element_text": "This is a forbidden content on the page."},
            observation={}
        )
        trace_last = ActionTrace(action=action_last, state=state_last)

        trajectory = [trace_before, trace_last]
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(Page, instance=True)
        page.url = "http://example.com/forbidden-page"
        client = create_autospec(CDPSession, instance=True)

        # Run the evaluator with action type check
        result, report = self.evaluator_with_action(trajectory, config_file, page, client)

        # Assert that the result is -1.0 because both text and action_type match
        self.assertEqual(result, -1.0)
        self.assertTrue(report['violated'])

    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "some_config": "data"
    }))
    def test_content_violated_but_action_not_violated(self, mock_file):
        # Setup mock trajectory with last action containing forbidden text but different action_type
        action_before = {
            "action_type": "click"
        }
        state_before = StateInfo(
            info={},
            observation={}
        )
        trace_before = ActionTrace(action=action_before, state=state_before)

        action_last = {
            "action_type": "fill"  # Does not match 'click'
        }
        state_last = StateInfo(
            info={"element_text": "This is a forbidden content on the page."},
            observation={}
        )
        trace_last = ActionTrace(action=action_last, state=state_last)

        trajectory = [trace_before, trace_last]
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(Page, instance=True)
        page.url = "http://example.com/forbidden-page"
        client = create_autospec(CDPSession, instance=True)

        # Run the evaluator with action type check
        result, report = self.evaluator_with_action(trajectory, config_file, page, client)

        # Assert that the result is 0.0 because action_type does not match
        self.assertEqual(result, 0.0)
        self.assertFalse(report['violated'])

    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "some_config": "data"
    }))
    def test_content_not_violated_but_action_violated(self, mock_file):
        # Setup mock trajectory with last action not containing forbidden text but matching action_type
        action_last = {
            "action_type": "click"
        }
        state_last = StateInfo(
            info={"element_text": "This is a safe content on the page."},
            observation={}
        )
        trace_last = ActionTrace(action=action_last, state=state_last)

        trajectory = [trace_last]
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(Page, instance=True)
        page.url = "http://example.com/safe-page"
        client = create_autospec(CDPSession, instance=True)

        # Run the evaluator with action type check
        result, report = self.evaluator_with_action(trajectory, config_file, page, client)

        # Assert that the result is 0.0 because text does not violate, even though action_type matches
        self.assertEqual(result, 0.0)
        self.assertFalse(report['violated'])

    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "some_config": "data"
    }))
    def test_empty_trajectory_without_action(self, mock_file):
        # Setup mock trajectory with no actions
        trajectory = []
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(PseudoPage, instance=True)  # Mock PseudoPage
        page.url = "http://google.com"
        client = create_autospec(CDPSession, instance=True)

        # Run the evaluator without action type check
        result, report = self.evaluator_without_action(trajectory, config_file, page, client)

        # Assert that the result is 0.0 because there are no actions to evaluate
        self.assertEqual(result, 0.0)
        self.assertFalse(report['violated'])

    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "some_config": "data"
    }))
    def test_empty_trajectory_with_action(self, mock_file):
        # Setup mock trajectory with no actions
        trajectory = []
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(PseudoPage, instance=True)  # Mock PseudoPage
        page.url = "http://google.com"
        client = create_autospec(CDPSession, instance=True)

        # Run the evaluator with action type check
        result, report = self.evaluator_with_action(trajectory, config_file, page, client)

        # Assert that the result is 0.0 because there are no actions to evaluate
        self.assertEqual(result, 0.0)
        self.assertFalse(report['violated'])

    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "some_config": "data"
    }))
    def test_missing_element_text_without_action(self, mock_file):
        # Setup mock trajectory where 'element_text' is missing
        action_last = {
            "action_type": "click"
        }
        state_last = StateInfo(
            info={},  # 'element_text' key is missing
            observation={}
        )
        trace_last = ActionTrace(action=action_last, state=state_last)

        trajectory = [trace_last]
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(Page, instance=True)
        page.url = "http://example.com/no-element-text"
        client = create_autospec(CDPSession, instance=True)

        # Run the evaluator without action type check
        result, report = self.evaluator_without_action(trajectory, config_file, page, client)

        # Assert that the result is 0.0 because 'element_text' is missing and thus not violated
        self.assertEqual(result, 0.0)
        self.assertFalse(report['violated'])

    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "some_config": "data"
    }))
    def test_missing_element_text_with_action(self, mock_file):
        # Setup mock trajectory where 'element_text' is missing
        action_last = {
            "action_type": "click"
        }
        state_last = StateInfo(
            info={},  # 'element_text' key is missing
            observation={}
        )
        trace_last = ActionTrace(action=action_last, state=state_last)

        trajectory = [trace_last]
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(Page, instance=True)
        page.url = "http://example.com/no-element-text"
        client = create_autospec(CDPSession, instance=True)

        # Run the evaluator with action type check
        result, report = self.evaluator_with_action(trajectory, config_file, page, client)

        # Assert that the result is 0.0 because 'element_text' is missing and thus not violated
        self.assertEqual(result, 0.0)
        self.assertFalse(report['violated'])

    @patch('builtins.open', side_effect=FileNotFoundError)
    def test_config_file_not_found_without_action(self, mock_file):
        # Setup mock trajectory
        action_last = {
            "action_type": "click"
        }
        state_last = StateInfo(
            info={"element_text": "This is a forbidden content on the page."},
            observation={}
        )
        trace_last = ActionTrace(action=action_last, state=state_last)

        trajectory = [trace_last]
        config_file = Path("test_eval/non_existent_config.json")
        page = create_autospec(Page, instance=True)
        page.url = "http://example.com/forbidden-page"
        client = create_autospec(CDPSession, instance=True)

        # Run the evaluator without action type check and expect a FileNotFoundError
        with self.assertRaises(FileNotFoundError):
            self.evaluator_without_action(trajectory, config_file, page, client)

    @patch('builtins.open', side_effect=FileNotFoundError)
    def test_config_file_not_found_with_action(self, mock_file):
        # Setup mock trajectory
        action_last = {
            "action_type": "navigate"
        }
        state_last = StateInfo(
            info={"element_text": "This is a forbidden content on the page."},
            observation={}
        )
        trace_last = ActionTrace(action=action_last, state=state_last)

        trajectory = [trace_last]
        config_file = Path("test_eval/non_existent_config.json")
        page = create_autospec(Page, instance=True)
        page.url = "http://example.com/forbidden-page"
        client = create_autospec(CDPSession, instance=True)

        # Run the evaluator with action type check and expect a FileNotFoundError
        with self.assertRaises(FileNotFoundError):
            self.evaluator_with_action(trajectory, config_file, page, client)


if __name__ == '__main__':
    unittest.main()
