import unittest
from unittest.mock import Mock, patch, mock_open, create_autospec
from pathlib import Path
import json

from playwright.sync_api import Page, CDPSession

from stwebagentbench.browser_env import StateInfo
from stwebagentbench.browser_env.custom_env import ActionTrace
from stwebagentbench.evaluation_harness import CountActionEvaluator
from stwebagentbench.evaluation_harness.helper_functions import PseudoPage  # Adjust import based on your setup


# Assuming imports for classes Trajectory, ActionTrace, Page, PseudoPage, CDPSession, and create_report_point

class TestCountActionEvaluator(unittest.TestCase):

    def setUp(self):
        self.params = {
            "eval": {
                "action_type": "click",
                "global_count": 2,
                # "element_selectors": ["#button1", "#button2"]  # We'll test with and without this
            }
        }
        self.evaluator = CountActionEvaluator(self.params)

    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "some_config": "data"
    }))
    def test_no_element_selectors_with_trajectory_of_size_3(self, mock_file):
        # Setup mock trajectory with three actions of type 'click'
        action1 = {
            "action_type": "click"
        }
        state1 = StateInfo(
            info={"element_bid": "button1"},
            observation={}
        )
        trace1 = ActionTrace(action=action1, state=state1)

        action2 = {
            "action_type": "click"
        }
        state2 = StateInfo(
            info={"element_bid": "button2"},
            observation={}
        )
        trace2 = ActionTrace(action=action2, state=state2)

        action3 = {
            "action_type": "type"
        }
        state3 = StateInfo(
            info={"element_bid": "input1"},
            observation={}
        )
        trace3 = ActionTrace(action=action3, state=state3)

        trajectory = [trace1, trace2, trace3]
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(Page, instance=True)  # Mock Page
        client = create_autospec(CDPSession, instance=True)  # Mock CDPSession

        # Run the evaluator
        result, report = self.evaluator(trajectory, config_file, page, client)

        # Assert that the result is -1.0 because the actual count (2) does not match expected_count (2)
        # Since we have 2 'click' actions, and expected count is 2, there should be no violation
        self.assertEqual(result, 0.0)
        self.assertFalse(report['violated'])

    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "some_config": "data"
    }))
    def test_no_element_selectors_with_empty_trajectory(self, mock_file):
        # Empty trajectory
        trajectory = []
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(Page, instance=True)  # Mock Page
        client = create_autospec(CDPSession, instance=True)  # Mock CDPSession

        # Run the evaluator
        result, report = self.evaluator(trajectory, config_file, page, client)

        # Assert that the result is -1.0 because the actual count (0) does not match expected_count (2)
        self.assertEqual(result, -1.0)
        self.assertTrue(report['violated'])

    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "some_config": "data"
    }))
    def test_element_selectors_with_trajectory_of_size_5(self, mock_file):
        # Update params to include element_selectors
        self.params['eval']['element_selectors'] = ['#button1', '#button2']
        self.evaluator = CountActionEvaluator(self.params)

        # Mock page to return specific bids for selectors
        page = create_autospec(Page, instance=True)
        page.query_selector.side_effect = lambda selector: Mock(get_attribute=lambda attr: selector.strip('#'))

        # Mock get_element_bid_by_selector to return bids based on selectors
        def mock_get_element_bid_by_selector(page, selector):
            return selector.strip('#')

        # Patch the get_element_bid_by_selector function
        with patch('stwebagentbench.evaluation_harness.evaluators.get_element_bid_by_selector',
                   side_effect=mock_get_element_bid_by_selector):
            # Setup mock trajectory with five actions
            action1 = {
                "action_type": "click"
            }
            state1 = StateInfo(
                info={"element_bid": "button1"},
                observation={}
            )
            trace1 = ActionTrace(action=action1, state=state1)

            action2 = {
                "action_type": "click"
            }
            state2 = StateInfo(
                info={"element_bid": "button2"},
                observation={}
            )
            trace2 = ActionTrace(action=action2, state=state2)

            action3 = {
                "action_type": "click"
            }
            state3 = StateInfo(
                info={"element_bid": "button3"},
                observation={}
            )
            trace3 = ActionTrace(action=action3, state=state3)

            action4 = {
                "action_type": "type"
            }
            state4 = StateInfo(
                info={"element_bid": "input1"},
                observation={}
            )
            trace4 = ActionTrace(action=action4, state=state4)

            action5 = {
                "action_type": "click"
            }
            state5 = StateInfo(
                info={"element_bid": "button1"},
                observation={}
            )
            trace5 = ActionTrace(action=action5, state=state5)

            trajectory = [trace1, trace2, trace3, trace4, trace5]
            config_file = Path("test_eval/fake_config.json")
            client = create_autospec(CDPSession, instance=True)  # Mock CDPSession

            # Run the evaluator
            result, report = self.evaluator(trajectory, config_file, page, client)

            # We have 3 'click' actions on target elements ('button1' and 'button2')
            # Since expected_count is 2, and actual is 3, there should be a violation
            self.assertEqual(result, -1.0)
            self.assertTrue(report['violated'])


    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "some_config": "data"
    }))
    def test_element_selectors_with_trajectory_of_size_5_less_than(self, mock_file):
        # Update params to include element_selectors
        params = {'eval':{}}
        params['eval']['element_selectors'] = ['#button1', '#button2']
        params['eval']['global_count_less_than'] = 3
        params['eval']['action_type'] = "click"

        self.evaluator = CountActionEvaluator(params)

        # Mock page to return specific bids for selectors
        page = create_autospec(Page, instance=True)
        page.query_selector.side_effect = lambda selector: Mock(get_attribute=lambda attr: selector.strip('#'))

        # Mock get_element_bid_by_selector to return bids based on selectors
        def mock_get_element_bid_by_selector(page, selector):
            return selector.strip('#')

        # Patch the get_element_bid_by_selector function
        with patch('stwebagentbench.evaluation_harness.evaluators.get_element_bid_by_selector',
                   side_effect=mock_get_element_bid_by_selector):
            # Setup mock trajectory with five actions
            action1 = {
                "action_type": "click"
            }
            state1 = StateInfo(
                info={"element_bid": "button1"},
                observation={}
            )
            trace1 = ActionTrace(action=action1, state=state1)

            action2 = {
                "action_type": "click"
            }
            state2 = StateInfo(
                info={"element_bid": "button2"},
                observation={}
            )
            trace2 = ActionTrace(action=action2, state=state2)

            action3 = {
                "action_type": "click"
            }
            state3 = StateInfo(
                info={"element_bid": "button3"},
                observation={}
            )
            trace3 = ActionTrace(action=action3, state=state3)

            action4 = {
                "action_type": "type"
            }
            state4 = StateInfo(
                info={"element_bid": "input1"},
                observation={}
            )
            trace4 = ActionTrace(action=action4, state=state4)

            action5 = {
                "action_type": "click"
            }
            state5 = StateInfo(
                info={"element_bid": "button1"},
                observation={}
            )
            trace5 = ActionTrace(action=action5, state=state5)

            trajectory = [trace1, trace2, trace3, trace4, trace5]
            config_file = Path("test_eval/fake_config.json")
            client = create_autospec(CDPSession, instance=True)  # Mock CDPSession

            # Run the evaluator
            result, report = self.evaluator(trajectory, config_file, page, client)

            # We have 3 'click' actions on target elements ('button1' and 'button2')
            # Since expected_count is 2, and actual is 3, there should be a violation
            self.assertEqual(result, -1.0)
            self.assertTrue(report['violated'])

    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "some_config": "data"
    }))
    def test_element_selectors_with_trajectory_of_size_5_less_than_not_violated(self, mock_file):
        # Update params to include element_selectors
        params = {'eval':{}}
        params['eval']['element_selectors'] = ['#button1', '#button2']
        params['eval']['global_count_less_than'] = 6
        params['eval']['action_type'] = "click"

        self.evaluator = CountActionEvaluator(params)

        # Mock page to return specific bids for selectors
        page = create_autospec(Page, instance=True)
        page.query_selector.side_effect = lambda selector: Mock(get_attribute=lambda attr: selector.strip('#'))

        # Mock get_element_bid_by_selector to return bids based on selectors
        def mock_get_element_bid_by_selector(page, selector):
            return selector.strip('#')

        # Patch the get_element_bid_by_selector function
        with patch('stwebagentbench.evaluation_harness.evaluators.get_element_bid_by_selector',
                   side_effect=mock_get_element_bid_by_selector):
            # Setup mock trajectory with five actions
            action1 = {
                "action_type": "click"
            }
            state1 = StateInfo(
                info={"element_bid": "button1"},
                observation={}
            )
            trace1 = ActionTrace(action=action1, state=state1)

            action2 = {
                "action_type": "click"
            }
            state2 = StateInfo(
                info={"element_bid": "button2"},
                observation={}
            )
            trace2 = ActionTrace(action=action2, state=state2)

            action3 = {
                "action_type": "click"
            }
            state3 = StateInfo(
                info={"element_bid": "button3"},
                observation={}
            )
            trace3 = ActionTrace(action=action3, state=state3)

            action4 = {
                "action_type": "type"
            }
            state4 = StateInfo(
                info={"element_bid": "input1"},
                observation={}
            )
            trace4 = ActionTrace(action=action4, state=state4)

            action5 = {
                "action_type": "click"
            }
            state5 = StateInfo(
                info={"element_bid": "button1"},
                observation={}
            )
            trace5 = ActionTrace(action=action5, state=state5)

            trajectory = [trace1, trace2, trace3, trace4, trace5]
            config_file = Path("test_eval/fake_config.json")
            client = create_autospec(CDPSession, instance=True)  # Mock CDPSession

            # Run the evaluator
            result, report = self.evaluator(trajectory, config_file, page, client)

            # We have 3 'click' actions on target elements ('button1' and 'button2')
            # Since expected_count is 2, and actual is 3, there should be a violation
            self.assertEqual(result, 0.0)
            self.assertFalse(report['violated'])

    @patch('builtins.open', new_callable=mock_open, read_data=json.dumps({
        "some_config": "data"
    }))
    def test_no_element_selectors_with_trajectory_of_size_5(self, mock_file):
        # Setup mock trajectory with five actions
        action1 = {
            "action_type": "click"
        }
        state1 = StateInfo(
            info={"element_bid": "button1"},
            observation={}
        )
        trace1 = ActionTrace(action=action1, state=state1)

        action2 = {
            "action_type": "click"
        }
        state2 = StateInfo(
            info={"element_bid": "button2"},
            observation={}
        )
        trace2 = ActionTrace(action=action2, state=state2)

        action3 = {
            "action_type": "click"
        }
        state3 = StateInfo(
            info={"element_bid": "button3"},
            observation={}
        )
        trace3 = ActionTrace(action=action3, state=state3)

        action4 = {
            "action_type": "type"
        }
        state4 = StateInfo(
            info={"element_bid": "input1"},
            observation={}
        )
        trace4 = ActionTrace(action=action4, state=state4)

        action5 = {
            "action_type": "click"
        }
        state5 = StateInfo(
            info={"element_bid": "button4"},
            observation={}
        )
        trace5 = ActionTrace(action=action5, state=state5)

        trajectory = [trace1, trace2, trace3, trace4, trace5]
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(Page, instance=True)  # Mock Page
        client = create_autospec(CDPSession, instance=True)  # Mock CDPSession

        # Run the evaluator
        result, report = self.evaluator(trajectory, config_file, page, client)

        # We have 4 'click' actions in total, expected is 2, so violation should occur
        self.assertEqual(result, -1.0)
        self.assertTrue(report['violated'])
