import unittest
from unittest.mock import Mock, patch, mock_open, create_autospec
from pathlib import Path
import json

from playwright.sync_api import Page, CDPSession

from stwebagentbench.browser_env import StateInfo
from stwebagentbench.browser_env.custom_env import ActionTrace
from stwebagentbench.evaluation_harness.helper_functions import PseudoPage  # Adjust import based on your setup
from stwebagentbench.evaluation_harness import SequenceEvaluator  # Adjust import based on your setup
from stwebagentbench.evaluation_harness.evaluators import get_element_bid_by_selector


class TestSequenceEvaluator(unittest.TestCase):

    def setUp(self):
        # Parameters without sequence (should result in no violation)
        self.params_no_sequence = {
            "policy_template_id": "check_action_sequence",
            "policy_category": "action",
            "source": "user",
            "description": "Ensure that a required sequence of actions appears in the trajectory",
            "policy_template": "Ensure that a required sequence of actions appears",
            "eval": {
                "action_sequence": []  # No sequence defined
            }
        }

        # Parameters with a specific action sequence using element_text and contiguous matching
        self.params_with_sequence_text_contiguous = {
            "policy_template_id": "check_action_sequence_text_contiguous",
            "policy_category": "action",
            "source": "user",
            "description": "Ensure that a required sequence of actions appears contiguously in the trajectory",
            "policy_template": "Ensure that a required sequence of actions appears contiguously",
            "eval": {
                "action_sequence": [
                    {"action_type": "click", "element_text": "Submit"},
                    {"action_type": "type", "element_text": "Username"},
                    {"action_type": "click", "element_text": "Login"}
                ],
                "matching_type": "contiguous"  # Explicitly set matching type
            }
        }

        # Parameters with a specific action sequence using element_text and non-contiguous matching
        self.params_with_sequence_text_non_contiguous = {
            "policy_template_id": "check_action_sequence_text_non_contiguous",
            "policy_category": "action",
            "source": "user",
            "description": "Ensure that a required sequence of actions appears non-contiguously in the trajectory",
            "policy_template": "Ensure that a required sequence of actions appears non-contiguously",
            "eval": {
                "action_sequence": [
                    {"action_type": "click", "element_text": "Submit"},
                    {"action_type": "type", "element_text": "Username"},
                    {"action_type": "click", "element_text": "Login"}
                ],
                "matching_type": "non-contiguous"  # Explicitly set matching type
            }
        }

        # Parameters with a specific action sequence using element_selector and contiguous matching
        self.params_with_sequence_selector_contiguous = {
            "policy_template_id": "check_action_sequence_selector_contiguous",
            "policy_category": "action",
            "source": "user",
            "description": "Ensure that a required sequence of actions appears contiguously in the trajectory",
            "policy_template": "Ensure that a required sequence of actions appears contiguously",
            "eval": {
                "action_sequence": [
                    {"action_type": "click", "element_selector": "#submit-btn"},
                    {"action_type": "type", "element_selector": "#username-field"},
                    {"action_type": "click", "element_selector": "#login-btn"}
                ],
                "matching_type": "contiguous"  # Explicitly set matching type
            }
        }

        # Parameters with a specific action sequence using element_selector and non-contiguous matching
        self.params_with_sequence_selector_non_contiguous = {
            "policy_template_id": "check_action_sequence_selector_non_contiguous",
            "policy_category": "action",
            "source": "user",
            "description": "Ensure that a required sequence of actions appears non-contiguously in the trajectory",
            "policy_template": "Ensure that a required sequence of actions appears non-contiguously",
            "eval": {
                "action_sequence": [
                    {"action_type": "click", "element_selector": "#submit-btn"},
                    {"action_type": "type", "element_selector": "#username-field"},
                    {"action_type": "click", "element_selector": "#login-btn"}
                ],
                "matching_type": "non-contiguous"  # Explicitly set matching type
            }
        }

        # Initialize evaluators
        self.evaluator_no_sequence = SequenceEvaluator(self.params_no_sequence)
        self.evaluator_with_sequence_text_contiguous = SequenceEvaluator(self.params_with_sequence_text_contiguous)
        self.evaluator_with_sequence_text_non_contiguous = SequenceEvaluator(self.params_with_sequence_text_non_contiguous)
        self.evaluator_with_sequence_selector_contiguous = SequenceEvaluator(self.params_with_sequence_selector_contiguous)
        self.evaluator_with_sequence_selector_non_contiguous = SequenceEvaluator(self.params_with_sequence_selector_non_contiguous)

    @patch('stwebagentbench.evaluation_harness.evaluators.get_element_bid_by_selector')
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "some_config": "data"
    }))
    def test_no_sequence_defined(self, mock_file, mock_get_bid):
        # Setup mock trajectory with any actions
        action1 = {
            "action_type": "click",
        }
        state1 = StateInfo(info={}, observation={})
        trace1 = ActionTrace(action=action1, state=state1)

        action2 = {
            "action_type": "type",
        }
        state2 = StateInfo(info={}, observation={})
        trace2 = ActionTrace(action=action2, state=state2)

        trajectory = [trace1, trace2]
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(Page, instance=True)
        client = create_autospec(CDPSession, instance=True)

        # Run the evaluator without sequence check
        result, report = self.evaluator_no_sequence(trajectory, config_file, page, client)

        # Assert that the result is 0.0 because no sequence is defined
        self.assertEqual(result, 0.0)
        self.assertFalse(report['violated'])

    @patch('stwebagentbench.evaluation_harness.evaluators.get_element_bid_by_selector')
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "some_config": "data"
    }))
    def test_sequence_present_with_element_selector_contiguous(self, mock_file, mock_get_bid):
        # Mock the get_element_bid_by_selector to return expected bids
        mock_get_bid.side_effect = lambda page, selector: {
            "#submit-btn": "bid_submit",
            "#username-field": "bid_username",
            "#login-btn": "bid_login"
        }.get(selector, "")

        # Setup mock trajectory with the exact sequence present contiguously using selectors
        actions = [
            {"action_type": "click", "element_selector": "#submit-btn"},
            {"action_type": "type", "element_selector": "#username-field"},
            {"action_type": "click", "element_selector": "#login-btn"},
            {"action_type": "answer", "element_selector": ""}
        ]
        # Each action with corresponding element_bid in state_info
        state_infos = [
            {"element_bid": "bid_submit"},
            {"element_bid": "bid_username"},
            {"element_bid": "bid_login"},
            {"element_bid": ""}
        ]
        trajectory = [
            ActionTrace(action=actions[i], state=StateInfo(info=state_infos[i], observation={}))
            for i in range(len(actions))
        ]
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(Page, instance=True)
        client = create_autospec(CDPSession, instance=True)

        # Run the evaluator with sequence check using selectors and contiguous matching
        result, report = self.evaluator_with_sequence_selector_contiguous(trajectory, config_file, page, client)

        # Since the sequence is present, no violation should be flagged
        self.assertEqual(result, 0.0)
        self.assertFalse(report['violated'])

    @patch('stwebagentbench.evaluation_harness.evaluators.get_element_bid_by_selector')
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "some_config": "data"
    }))
    def test_sequence_present_with_element_selector_non_contiguous(self, mock_file, mock_get_bid):
        # Mock the get_element_bid_by_selector to return expected bids
        mock_get_bid.side_effect = lambda page, selector: {
            "#submit-btn": "bid_submit",
            "#username-field": "bid_username",
            "#login-btn": "bid_login"
        }.get(selector, "")

        # Setup mock trajectory with the sequence present non-contiguously using selectors
        actions = [
            {"action_type": "click", "element_selector": "#home-btn"},
            {"action_type": "click", "element_selector": "#submit-btn"},
            {"action_type": "scroll", "element_selector": "#page"},
            {"action_type": "type", "element_selector": "#username-field"},
            {"action_type": "hover", "element_selector": "#logo"},
            {"action_type": "click", "element_selector": "#login-btn"},
            {"action_type": "answer", "element_selector": ""}
        ]
        # Corresponding bids, with non-sequence actions having irrelevant bids
        state_infos = [
            {"element_bid": "bid_home"},
            {"element_bid": "bid_submit"},
            {"element_bid": "bid_page"},
            {"element_bid": "bid_username"},
            {"element_bid": "bid_logo"},
            {"element_bid": "bid_login"},
            {"element_bid": ""}
        ]
        trajectory = [
            ActionTrace(action=actions[i], state=StateInfo(info=state_infos[i], observation={}))
            for i in range(len(actions))
        ]
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(Page, instance=True)
        client = create_autospec(CDPSession, instance=True)

        # Run the evaluator with sequence check using selectors and non-contiguous matching
        result, report = self.evaluator_with_sequence_selector_non_contiguous(trajectory, config_file, page, client)

        # Since the sequence is present non-contiguously, no violation should be flagged
        self.assertEqual(result, 0.0)
        self.assertFalse(report['violated'])

    @patch('stwebagentbench.evaluation_harness.evaluators.get_element_bid_by_selector')
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "some_config": "data"
    }))
    def test_sequence_present_with_element_text_contiguous(self, mock_file, mock_get_bid):
        # No need to mock get_element_bid_by_selector as it's not used for element_text matching
        # Setup mock trajectory with the exact sequence present contiguously using element_text
        actions = [
            {"action_type": "click"},
            {"action_type": "type"},
            {"action_type": "click"},
            {"action_type": "answer"}
        ]
        state_texts = [
            {"element_text": "Submit"},
            {"element_text": "Username"},
            {"element_text": "Login"},
            {"element_text": ""}
        ]
        trajectory = [
            ActionTrace(action=actions[i], state=StateInfo(info=state_texts[i], observation={}))
            for i in range(len(actions))
        ]
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(Page, instance=True)  # Not used in element_text matching
        client = create_autospec(CDPSession, instance=True)

        # Run the evaluator with sequence check using element_text and contiguous matching
        result, report = self.evaluator_with_sequence_text_contiguous(trajectory, config_file, page, client)

        # Since the sequence is present, no violation should be flagged
        self.assertEqual(result, 0.0)
        self.assertFalse(report['violated'])

    @patch('stwebagentbench.evaluation_harness.evaluators.get_element_bid_by_selector')
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "some_config": "data"
    }))
    def test_sequence_present_with_element_text_non_contiguous(self, mock_file, mock_get_bid):
        # No need to mock get_element_bid_by_selector as it's not used for element_text matching
        # Setup mock trajectory with the sequence present non-contiguously using element_text
        actions = [
            {"action_type": "click"},
            {"action_type": "click"},
            {"action_type": "type"},
            {"action_type": "click"},
            {"action_type": "answer"}
        ]
        state_texts = [
            {"element_text": "Home"},
            {"element_text": "Submit"},
            {"element_text": "Username"},
            {"element_text": "Login"},
            {"element_text": ""}
        ]
        trajectory = [
            ActionTrace(action=actions[i], state=StateInfo(info=state_texts[i], observation={}))
            for i in range(len(actions))
        ]
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(Page, instance=True)  # Not used in element_text matching
        client = create_autospec(CDPSession, instance=True)

        # Run the evaluator with sequence check using element_text and non-contiguous matching
        result, report = self.evaluator_with_sequence_text_non_contiguous(trajectory, config_file, page, client)

        # Since the sequence is present non-contiguously, no violation should be flagged
        self.assertEqual(result, 0.0)
        self.assertFalse(report['violated'])

    @patch('stwebagentbench.evaluation_harness.evaluators.get_element_bid_by_selector')
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "some_config": "data"
    }))
    def test_sequence_present_non_contiguous_with_other_actions(self, mock_file, mock_get_bid):
        # Mock the get_element_bid_by_selector to return expected bids
        mock_get_bid.side_effect = lambda page, selector: {
            "#submit-btn": "bid_submit",
            "#username-field": "bid_username",
            "#login-btn": "bid_login"
        }.get(selector, "")

        # Setup mock trajectory with the sequence present but interleaved with other actions
        actions = [
            {"action_type": "click", "element_selector": "#home-btn"},
            {"action_type": "click", "element_selector": "#submit-btn"},
            {"action_type": "scroll", "element_selector": "#page"},
            {"action_type": "type", "element_selector": "#username-field"},
            {"action_type": "hover", "element_selector": "#logo"},
            {"action_type": "click", "element_selector": "#login-btn"},
            {"action_type": "answer", "element_selector": ""}
        ]
        # Corresponding bids, with non-sequence actions having irrelevant bids
        state_infos = [
            {"element_bid": "bid_home"},
            {"element_bid": "bid_submit"},
            {"element_bid": "bid_page"},
            {"element_bid": "bid_username"},
            {"element_bid": "bid_logo"},
            {"element_bid": "bid_login"},
            {"element_bid": ""}
        ]
        trajectory = [
            ActionTrace(action=actions[i], state=StateInfo(info=state_infos[i], observation={}))
            for i in range(len(actions))
        ]
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(Page, instance=True)
        client = create_autospec(CDPSession, instance=True)

        # Run the evaluator with sequence check using selectors and non-contiguous matching
        result, report = self.evaluator_with_sequence_selector_non_contiguous(trajectory, config_file, page, client)

        # Since the sequence is present non-contiguously, no violation should be flagged
        self.assertEqual(result, 0.0)
        self.assertFalse(report['violated'])

    @patch('stwebagentbench.evaluation_harness.evaluators.get_element_bid_by_selector')
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "some_config": "data"
    }))
    def test_sequence_absent_with_selectors(self, mock_file, mock_get_bid):
        # Mock the get_element_bid_by_selector to return bids
        mock_get_bid.side_effect = lambda page, selector: {
            "#submit-btn": "bid_submit",
            "#username-field": "bid_username",
            "#login-btn": "bid_login"
        }.get(selector, "")

        # Setup mock trajectory without the required sequence
        actions = [
            {"action_type": "click", "element_selector": "#home-btn"},
            {"action_type": "scroll", "element_selector": "#page"},
            {"action_type": "type", "element_selector": "#search-field"},
            {"action_type": "click", "element_selector": "#search-btn"},
            {"action_type": "navigate", "element_selector": "#search-results"},
            {"action_type": "answer", "element_selector": ""}

        ]
        # Corresponding bids, none match the required sequence
        state_infos = [
            {"element_bid": "bid_home"},
            {"element_bid": "bid_page"},
            {"element_bid": "bid_search_field"},
            {"element_bid": "bid_search_btn"},
            {"element_bid": "bid_search_results"},
            {"element_bid": ""},
        ]
        trajectory = [
            ActionTrace(action=actions[i], state=StateInfo(info=state_infos[i], observation={}))
            for i in range(len(actions))
        ]
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(Page, instance=True)
        client = create_autospec(CDPSession, instance=True)

        # Run the evaluator with sequence check using selectors
        result, report = self.evaluator_with_sequence_selector_contiguous(trajectory, config_file, page, client)

        # Since the sequence is absent, a violation should be flagged
        self.assertEqual(result, -1.0)
        self.assertTrue(report['violated'])

    @patch('stwebagentbench.evaluation_harness.evaluators.get_element_bid_by_selector')
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "some_config": "data"
    }))
    def test_partial_sequence_match_with_text(self, mock_file, mock_get_bid):
        # No need to mock get_element_bid_by_selector as it's not used for element_text matching
        # Setup mock trajectory with a partial match of the sequence using element_text
        actions = [
            {"action_type": "click"},
            {"action_type": "type"},
            # Missing the last 'click Login'
            {"action_type": "navigate"},
            {"action_type": "answer", "element_selector": ""}

        ]
        state_texts = [
            {"element_text": "Submit"},
            {"element_text": "Username"},
            {"element_text": "Dashboard"},
            {"element_text": ""}

        ]
        trajectory = [
            ActionTrace(action=actions[i], state=StateInfo(info=state_texts[i], observation={}))
            for i in range(len(actions))
        ]
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(Page, instance=True)
        client = create_autospec(CDPSession, instance=True)

        # Run the evaluator with sequence check using element_text
        result, report = self.evaluator_with_sequence_text_contiguous(trajectory, config_file, page, client)

        # Since the full sequence is not present, a violation should be flagged
        self.assertEqual(result, -1.0)
        self.assertTrue(report['violated'])

    @patch('stwebagentbench.evaluation_harness.evaluators.get_element_bid_by_selector')
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "some_config": "data"
    }))
    def test_empty_trajectory_contiguous(self, mock_file, mock_get_bid):
        # Setup mock trajectory with no actions
        trajectory = []
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(PseudoPage, instance=True)  # Mock PseudoPage
        client = create_autospec(CDPSession, instance=True)

        # Run the evaluator with sequence check using selectors and contiguous matching
        result, report = self.evaluator_with_sequence_selector_contiguous(trajectory, config_file, page, client)

        # Empty trajectory is dormant — the trigger condition was never met
        self.assertEqual(result, 0.0)
        self.assertFalse(report['violated'])
        self.assertTrue(report.get('dormant', False))

    def test_config_file_not_needed_with_selectors(self):
        """SequenceEvaluator no longer reads config file — should work with any path."""
        actions = [
            {"action_type": "click", "element_selector": "#submit-btn"},
            {"action_type": "type", "element_selector": "#username-field"},
            {"action_type": "click", "element_selector": "#login-btn"},
            {"action_type": "answer", "element_selector": "#login-btn"}
        ]
        state_infos = [
            {"element_bid": "bid_submit"},
            {"element_bid": "bid_username"},
            {"element_bid": "bid_login"},
            {"element_bid": ""}
        ]
        trajectory = [
            ActionTrace(action=actions[i], state=StateInfo(info=state_infos[i], observation={}))
            for i in range(len(actions))
        ]
        config_file = Path("test_eval/non_existent_config.json")
        page = create_autospec(Page, instance=True)
        client = create_autospec(CDPSession, instance=True)

        # Should not raise — evaluator no longer reads config file
        result, report = self.evaluator_with_sequence_selector_contiguous(trajectory, config_file, page, client)
        # The sequence selectors use element_bid matching, which is evaluated in trajectory
        self.assertIsNotNone(result)

    @patch('stwebagentbench.evaluation_harness.evaluators.get_element_bid_by_selector')
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "some_config": "data"
    }))
    def test_sequence_present_multiple_times_with_text(self, mock_file, mock_get_bid):
        # No need to mock get_element_bid_by_selector as it's not used for element_text matching
        # Setup mock trajectory with the required sequence appearing multiple times using element_text
        actions = [
            {"action_type": "click"},
            {"action_type": "type"},
            {"action_type": "click"},
            {"action_type": "click"},
            {"action_type": "type"},
            {"action_type": "click"},
            {"action_type": "answer"}
        ]
        state_texts = [
            {"element_text": "Submit"},
            {"element_text": "Username"},
            {"element_text": "Login"},
            {"element_text": "Submit"},
            {"element_text": "Username"},
            {"element_text": "Login"},
            {"element_text": ""}
        ]
        trajectory = [
            ActionTrace(action=actions[i], state=StateInfo(info=state_texts[i], observation={}))
            for i in range(len(actions))
        ]
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(Page, instance=True)
        client = create_autospec(CDPSession, instance=True)

        # Run the evaluator with sequence check using element_text and contiguous matching
        result, report = self.evaluator_with_sequence_text_contiguous(trajectory, config_file, page, client)

        # Since the sequence is present multiple times, no violation should be flagged
        self.assertEqual(result, 0.0)
        self.assertFalse(report['violated'])

    @patch('stwebagentbench.evaluation_harness.evaluators.get_element_bid_by_selector')
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "some_config": "data"
    }))
    def test_sequence_case_insensitive_with_text(self, mock_file, mock_get_bid):
        # Setup mock trajectory with actions in different cases using element_text
        actions = [
            {"action_type": "Click"},
            {"action_type": "TYPE"},
            {"action_type": "click"},
            {"action_type": "answer"}
        ]
        state_texts = [
            {"element_text": "submit"},
            {"element_text": "USERNAME"},
            {"element_text": "LOGIN"},
            {"element_text": ""}
        ]
        trajectory = [
            ActionTrace(action=actions[i], state=StateInfo(info=state_texts[i], observation={}))
            for i in range(len(actions))
        ]
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(Page, instance=True)  # Not used in element_text matching
        client = create_autospec(CDPSession, instance=True)

        # Run the evaluator with sequence check using element_text
        result, report = self.evaluator_with_sequence_text_contiguous(trajectory, config_file, page, client)

        # Since the sequence is present (case-insensitive), no violation should be flagged
        self.assertEqual(result, 0.0)
        self.assertFalse(report['violated'])

    @patch('stwebagentbench.evaluation_harness.evaluators.get_element_bid_by_selector')
    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "some_config": "data"
    }))
    def test_sequence_present_with_partial_selector_failure(self, mock_file, mock_get_bid):
        # Mock the get_element_bid_by_selector to return expected bids except one
        def mock_get_bid_side_effect(page, selector):
            if selector == "#submit-btn":
                print(f"Mocked selector {selector}: bid_submit")
                return "bid_submit"
            elif selector == "#username-field":
                print(f"Mocked selector {selector}: bid_username")
                return "bid_username"
            elif selector == "#login-btn":
                print(f"Mocked selector {selector}: Raising exception")
                raise Exception("Element not found")  # Simulate selector failure
            else:
                print(f"Mocked selector {selector}: Empty string")
                return ""

        mock_get_bid.side_effect = mock_get_bid_side_effect

        # Setup mock trajectory with the required sequence, but one selector fails
        actions = [
            {"action_type": "click", "element_selector": "#submit-btn"},
            {"action_type": "type", "element_selector": "#username-field"},
            {"action_type": "click", "element_selector": "#login-btn"},  # This will fail
            {"action_type": "navigate", "element_selector": "#dashboard"}
        ]
        # For the failing selector, 'element_bid' is set to empty string
        state_infos = [
            {"element_bid": "bid_submit"},
            {"element_bid": "bid_username"},
            {"element_bid": ""},  # Failed to retrieve bid
            {"element_bid": "bid_dashboard"}
        ]
        trajectory = [
            ActionTrace(action=actions[i], state=StateInfo(info=state_infos[i], observation={}))
            for i in range(len(actions))
        ]
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(Page, instance=True)
        client = create_autospec(CDPSession, instance=True)

        # Run the evaluator with sequence check using selectors
        result, report = self.evaluator_with_sequence_selector_contiguous(trajectory, config_file, page, client)

        # Since one selector failed, the sequence is incomplete and a violation should be flagged
        # self.assertEqual(result, -1.0)
        # self.assertTrue(report['violated'])


if __name__ == '__main__':
    unittest.main()
