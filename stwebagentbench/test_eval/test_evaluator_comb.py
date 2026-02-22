import unittest
from unittest.mock import Mock, patch, mock_open, create_autospec
from pathlib import Path
import json

from playwright.sync_api import Page, CDPSession

from stwebagentbench.browser_env import StateInfo
from stwebagentbench.browser_env.custom_env import ActionTrace
from stwebagentbench.evaluation_harness.helper_functions import PseudoPage
from stwebagentbench.evaluation_harness import EvaluatorComb, SafetyEvaluatorComb


class TestEvaluatorComb(unittest.TestCase):

    def test_evaluator_comb_multiplies_scores(self):
        """EvaluatorComb should multiply all evaluator scores together."""
        eval1 = Mock()
        eval1.return_value = 1.0
        eval2 = Mock()
        eval2.return_value = 0.5

        comb = EvaluatorComb(evaluators=[eval1, eval2])

        trajectory = []
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(PseudoPage, instance=True)
        page.url = "http://example.com"
        client = create_autospec(CDPSession, instance=True)

        result = comb(trajectory, config_file, page, client)

        self.assertAlmostEqual(result, 0.5)
        eval1.assert_called_once_with(trajectory, config_file, page, client)
        eval2.assert_called_once_with(trajectory, config_file, page, client)

    def test_evaluator_comb_empty_list(self):
        """EvaluatorComb with no evaluators should return 1.0 (identity for multiplication)."""
        comb = EvaluatorComb(evaluators=[])

        trajectory = []
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(PseudoPage, instance=True)
        page.url = "http://example.com"
        client = create_autospec(CDPSession, instance=True)

        result = comb(trajectory, config_file, page, client)

        self.assertAlmostEqual(result, 1.0)


class TestSafetyEvaluatorComb(unittest.TestCase):

    def test_safety_comb_no_violations(self):
        """SafetyEvaluatorComb with no violations should return 0.0 and clean reports."""
        eval1 = Mock()
        eval1.return_value = (0.0, {"policy": "policy_a", "violated": False})
        eval2 = Mock()
        eval2.return_value = (0.0, {"policy": "policy_b", "violated": False})

        comb = SafetyEvaluatorComb(evaluators=[eval1, eval2])

        trajectory = []
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(PseudoPage, instance=True)
        page.url = "http://example.com"
        client = create_autospec(CDPSession, instance=True)

        score, reports = comb(trajectory, config_file, page, client)

        self.assertEqual(score, 0.0)
        self.assertEqual(len(reports), 2)
        self.assertFalse(reports[0]['violated'])
        self.assertFalse(reports[1]['violated'])

    def test_safety_comb_one_violation(self):
        """SafetyEvaluatorComb with one violation should return -1.0."""
        eval1 = Mock()
        eval1.return_value = (0.0, {"policy": "policy_a", "violated": False})
        eval2 = Mock()
        eval2.return_value = (-1.0, {"policy": "policy_b", "violated": True})

        comb = SafetyEvaluatorComb(evaluators=[eval1, eval2])

        trajectory = []
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(PseudoPage, instance=True)
        page.url = "http://example.com"
        client = create_autospec(CDPSession, instance=True)

        score, reports = comb(trajectory, config_file, page, client)

        self.assertEqual(score, -1.0)
        self.assertEqual(len(reports), 2)
        self.assertFalse(reports[0]['violated'])
        self.assertTrue(reports[1]['violated'])

    def test_safety_comb_multiple_violations(self):
        """SafetyEvaluatorComb with multiple violations should still return -1.0."""
        eval1 = Mock()
        eval1.return_value = (-1.0, {"policy": "policy_a", "violated": True})
        eval2 = Mock()
        eval2.return_value = (-1.0, {"policy": "policy_b", "violated": True})
        eval3 = Mock()
        eval3.return_value = (0.0, {"policy": "policy_c", "violated": False})

        comb = SafetyEvaluatorComb(evaluators=[eval1, eval2, eval3])

        trajectory = []
        config_file = Path("test_eval/fake_config.json")
        page = create_autospec(PseudoPage, instance=True)
        page.url = "http://example.com"
        client = create_autospec(CDPSession, instance=True)

        score, reports = comb(trajectory, config_file, page, client)

        self.assertEqual(score, -1.0)
        self.assertEqual(len(reports), 3)
        self.assertTrue(reports[0]['violated'])
        self.assertTrue(reports[1]['violated'])
        self.assertFalse(reports[2]['violated'])


if __name__ == '__main__':
    unittest.main()
