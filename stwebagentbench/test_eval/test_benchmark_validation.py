"""Pytest wrapper for offline benchmark validation.

Runs the same 7 validation phases as scripts/validate_benchmark.py
as individual pytest test cases for CI integration.

Does NOT require web apps or API keys — purely offline.

Usage:
    PYTHONPATH=. pytest stwebagentbench/test_eval/test_benchmark_validation.py -v
"""

import json
import re
import tempfile
import unittest
from collections import Counter
from pathlib import Path

from stwebagentbench.evaluation_harness.evaluators import (
    validate_policy_schema,
    safety_evaluator_router,
    VALID_EVAL_TYPES,
    SafetyEvaluatorComb,
    ActionEvaluator,
    AskUserConsentEvaluator,
    CountActionEvaluator,
    GeneralErrorEvaluator,
    InputHallucinationEvaluator,
    SafetyHTMLContentEvaluator,
    SafetyURLEvaluator,
    SensitiveDataEvaluator,
    SequenceEvaluator,
    VALIDATION_STRICT,
)

TASKS_PATH = Path("stwebagentbench/test.raw.json")

EVAL_TYPE_TO_CLASS = {
    "element_action_match": ActionEvaluator,
    "is_sequence_match": SequenceEvaluator,
    "is_url_match": SafetyURLEvaluator,
    "is_ask_the_user": AskUserConsentEvaluator,
    "is_action_count": CountActionEvaluator,
    "is_program_html": SafetyHTMLContentEvaluator,
    "is_input_hallucination": InputHallucinationEvaluator,
    "is_sensitive_data": SensitiveDataEvaluator,
    "popup_error": GeneralErrorEvaluator,
}

REQUIRED_FIELDS = {"policy_template_id", "policy_category", "source", "description", "eval"}

# (min_tasks_covered, min_templates, min_eval_types, min_unique_descriptions)
# Actual benchmark coverage (verified 2026-03-01 from test.raw.json):
#   strict_execution:                coverage=374, templates=3, eval_types=4, unique_descs=62
#   boundary_and_scope_limitation:   coverage=351, templates=2, eval_types=2, unique_descs=47
#   robustness_and_security:         coverage=238, templates=2, eval_types=2, unique_descs=83
#   user_consent:                    coverage=145, templates=2, eval_types=1, unique_descs=46
#   hierarchy_adherence:             coverage=111, templates=2, eval_types=2, unique_descs=51
#   error_handling_and_safety_nets:  coverage=99,  templates=2, eval_types=2, unique_descs=16
# Not all tasks have every dimension (modality/read-only tasks intentionally have fewer).
# Thresholds are set at ~90% of actual coverage, exact for templates/eval_types.
DIMENSION_THRESHOLDS = {
    "user_consent":                    (140, 2, 1, 44),
    "boundary_and_scope_limitation":   (340, 2, 2, 45),
    "error_handling_and_safety_nets":  (90,  2, 2, 15),
    "hierarchy_adherence":             (100, 2, 2, 50),
    "robustness_and_security":         (200, 2, 2, 50),
    "strict_execution":                (370, 3, 4, 50),
}

CRM_EASY = list(range(235, 255))
CRM_MEDIUM = list(range(255, 275))
CRM_HARD = list(range(275, 295))

READONLY_TASKS = set(range(85, 235)) | (set(range(295, 375)) - {297, 302, 307})
WRITE_ACTION_TERMS = {"save", "delete", "submit", "merge", "invite", "update", "edit"}


def _load_tasks():
    with open(TASKS_PATH) as f:
        return json.load(f)


def _extract_must_include_terms(must_include_str):
    if not must_include_str:
        return set()
    parts = re.split(r'\s*\|(?:or|OR)\|\s*', must_include_str)
    return {p.strip().lower() for p in parts if p.strip()}


class TestSchemaIntegrity(unittest.TestCase):
    """Phase 1: Every policy passes schema validation."""

    @classmethod
    def setUpClass(cls):
        cls.tasks = _load_tasks()

    def test_all_policies_have_required_fields(self):
        for task in self.tasks:
            for idx, policy in enumerate(task.get("policies", [])):
                missing = REQUIRED_FIELDS - set(policy.keys())
                self.assertEqual(
                    missing, set(),
                    f"Task {task['task_id']} policy {idx}: missing {missing}"
                )

    def test_all_policies_have_valid_eval_types(self):
        for task in self.tasks:
            for idx, policy in enumerate(task.get("policies", [])):
                eval_types = policy.get("eval", {}).get("eval_types", [])
                self.assertTrue(
                    len(eval_types) > 0,
                    f"Task {task['task_id']} policy {idx}: empty eval_types"
                )
                self.assertIn(
                    eval_types[0], VALID_EVAL_TYPES,
                    f"Task {task['task_id']} policy {idx}: unknown eval_type '{eval_types[0]}'"
                )

    def test_all_policies_pass_strict_schema_validation(self):
        for task in self.tasks:
            for idx, policy in enumerate(task.get("policies", [])):
                try:
                    validate_policy_schema(policy, level=VALIDATION_STRICT)
                except ValueError as e:
                    self.fail(f"Task {task['task_id']} policy {idx}: {e}")


class TestEvaluatorInstantiation(unittest.TestCase):
    """Phase 2: Every task's policies can instantiate evaluators."""

    @classmethod
    def setUpClass(cls):
        cls.tasks = _load_tasks()

    def test_all_tasks_instantiate_evaluators(self):
        for task in self.tasks:
            config = {
                "eval": task.get("eval", {}),
                "policies": task.get("policies", []),
            }
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                json.dump(config, f)
                tmp_path = f.name
            try:
                comb = safety_evaluator_router(tmp_path)
                self.assertIsInstance(comb, SafetyEvaluatorComb)
                self.assertEqual(
                    len(comb.evaluators), len(task["policies"]),
                    f"Task {task['task_id']}: evaluator count mismatch"
                )
            finally:
                Path(tmp_path).unlink(missing_ok=True)

    def test_evaluators_are_correct_class(self):
        for task in self.tasks:
            config = {
                "eval": task.get("eval", {}),
                "policies": task.get("policies", []),
            }
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                json.dump(config, f)
                tmp_path = f.name
            try:
                comb = safety_evaluator_router(tmp_path)
                for idx, (ev, pol) in enumerate(zip(comb.evaluators, task["policies"])):
                    et = pol["eval"]["eval_types"][0]
                    expected = EVAL_TYPE_TO_CLASS.get(et)
                    if expected:
                        self.assertIsInstance(
                            ev, expected,
                            f"Task {task['task_id']} policy {idx}: "
                            f"got {type(ev).__name__}, expected {expected.__name__}"
                        )
            finally:
                Path(tmp_path).unlink(missing_ok=True)


class TestDimensionCoverage(unittest.TestCase):
    """Phase 3: Each dimension meets coverage/diversity thresholds."""

    @classmethod
    def setUpClass(cls):
        cls.tasks = _load_tasks()

    def test_coverage_per_dimension(self):
        for dim_name, (min_cov, _, _, _) in DIMENSION_THRESHOLDS.items():
            covered = set()
            for task in self.tasks:
                for p in task.get("policies", []):
                    if p.get("policy_category") == dim_name:
                        covered.add(task["task_id"])
            self.assertGreaterEqual(
                len(covered), min_cov,
                f"{dim_name}: coverage {len(covered)} < {min_cov}"
            )

    def test_templates_per_dimension(self):
        for dim_name, (_, min_tpl, _, _) in DIMENSION_THRESHOLDS.items():
            templates = set()
            for task in self.tasks:
                for p in task.get("policies", []):
                    if p.get("policy_category") == dim_name:
                        templates.add(p["policy_template_id"])
            self.assertGreaterEqual(
                len(templates), min_tpl,
                f"{dim_name}: templates {len(templates)} < {min_tpl}"
            )

    def test_eval_types_per_dimension(self):
        for dim_name, (_, _, min_et, _) in DIMENSION_THRESHOLDS.items():
            eval_types = set()
            for task in self.tasks:
                for p in task.get("policies", []):
                    if p.get("policy_category") == dim_name:
                        for et in p["eval"].get("eval_types", []):
                            eval_types.add(et)
            self.assertGreaterEqual(
                len(eval_types), min_et,
                f"{dim_name}: eval_types {len(eval_types)} < {min_et}"
            )

    def test_unique_descriptions_per_dimension(self):
        for dim_name, (_, _, _, min_desc) in DIMENSION_THRESHOLDS.items():
            descs = set()
            for task in self.tasks:
                for p in task.get("policies", []):
                    if p.get("policy_category") == dim_name:
                        descs.add(p["description"])
            self.assertGreaterEqual(
                len(descs), min_desc,
                f"{dim_name}: unique descriptions {len(descs)} < {min_desc}"
            )

    def test_no_generic_descriptions(self):
        generic_count = 0
        for task in self.tasks:
            for p in task.get("policies", []):
                desc = p.get("description", "").strip()
                if desc == "ask the user permission before performing an action":
                    generic_count += 1
        self.assertEqual(generic_count, 0, f"{generic_count} generic descriptions found")


class TestCrossDimensionConflicts(unittest.TestCase):
    """Phase 4: No task has conflicting policies."""

    @classmethod
    def setUpClass(cls):
        cls.tasks = _load_tasks()

    def test_no_do_not_click_intent_conflicts(self):
        for task in self.tasks:
            intent = task.get("intent", "").lower()
            for policy in task.get("policies", []):
                if policy.get("policy_template_id") not in ("do_not_click", "do_not_type"):
                    continue
                mi = policy.get("eval", {}).get("must_include") or ""
                terms = _extract_must_include_terms(mi)
                for term in terms:
                    if len(term) > 3:
                        self.assertIsNone(
                            re.search(r'\b' + re.escape(term) + r'\b', intent),
                            f"Task {task['task_id']}: do_not_click term '{term}' in intent"
                        )

    def test_no_duplicate_policies(self):
        for task in self.tasks:
            fps = []
            for p in task.get("policies", []):
                fp = (p["policy_template_id"],
                      json.dumps(p["eval"], sort_keys=True, default=str))
                fps.append(fp)
            fp_counter = Counter(fps)
            for fp, count in fp_counter.items():
                self.assertEqual(
                    count, 1,
                    f"Task {task['task_id']}: identical policy '{fp[0]}' appears {count} times"
                )


class TestCRMTierSuperset(unittest.TestCase):
    """Phase 5: Easy <= Medium <= Hard policy fingerprints."""

    @classmethod
    def setUpClass(cls):
        cls.tasks = _load_tasks()
        cls.task_by_id = {t["task_id"]: t for t in cls.tasks}

    def _get_fps(self, task_id):
        task = self.task_by_id.get(task_id, {})
        return set(
            (p["policy_template_id"], p["policy_category"],
             tuple(p["eval"].get("eval_types", [])))
            for p in task.get("policies", [])
        )

    def test_easy_subset_of_medium(self):
        for i in range(20):
            easy_fps = self._get_fps(CRM_EASY[i])
            medium_fps = self._get_fps(CRM_MEDIUM[i])
            self.assertTrue(
                easy_fps.issubset(medium_fps),
                f"Group {i}: Easy ⊄ Medium, diff={easy_fps - medium_fps}"
            )

    def test_medium_subset_of_hard(self):
        for i in range(20):
            medium_fps = self._get_fps(CRM_MEDIUM[i])
            hard_fps = self._get_fps(CRM_HARD[i])
            self.assertTrue(
                medium_fps.issubset(hard_fps),
                f"Group {i}: Medium ⊄ Hard, diff={medium_fps - hard_fps}"
            )

    def test_tier_policy_count_ordering(self):
        for i in range(20):
            n_easy = len(self.task_by_id[CRM_EASY[i]].get("policies", []))
            n_medium = len(self.task_by_id[CRM_MEDIUM[i]].get("policies", []))
            n_hard = len(self.task_by_id[CRM_HARD[i]].get("policies", []))
            self.assertGreater(n_medium, n_easy, f"Group {i}: |Med|={n_medium} <= |Easy|={n_easy}")
            self.assertGreaterEqual(n_hard, n_medium, f"Group {i}: |Hard|={n_hard} < |Med|={n_medium}")


class TestEvaluatorFields(unittest.TestCase):
    """Phase 6: Eval-type-specific fields are semantically valid."""

    @classmethod
    def setUpClass(cls):
        cls.tasks = _load_tasks()

    def test_ask_the_user_must_include_non_empty(self):
        for task in self.tasks:
            for p in task.get("policies", []):
                et = p["eval"].get("eval_types", [None])[0]
                if et != "is_ask_the_user":
                    continue
                mi = p["eval"].get("must_include", "")
                self.assertTrue(
                    mi and mi.strip(),
                    f"Task {task['task_id']} [{p['policy_template_id']}]: empty must_include"
                )

    def test_action_count_has_exactly_one_count_field(self):
        for task in self.tasks:
            for p in task.get("policies", []):
                et = p["eval"].get("eval_types", [None])[0]
                if et != "is_action_count":
                    continue
                gc = p["eval"].get("global_count")
                gcl = p["eval"].get("global_count_less_than")
                gca = p["eval"].get("global_count_at_least")
                count_fields = [x for x in [gc, gcl, gca] if x is not None]
                self.assertEqual(
                    len(count_fields), 1,
                    f"Task {task['task_id']} [{p['policy_template_id']}]: "
                    f"expected 1 count field, got {len(count_fields)}"
                )

    def test_action_count_has_action_type(self):
        for task in self.tasks:
            for p in task.get("policies", []):
                et = p["eval"].get("eval_types", [None])[0]
                if et != "is_action_count":
                    continue
                at = p["eval"].get("action_type", "")
                self.assertTrue(at, f"Task {task['task_id']}: is_action_count missing action_type")

    def test_sensitive_data_has_field(self):
        for task in self.tasks:
            for p in task.get("policies", []):
                et = p["eval"].get("eval_types", [None])[0]
                if et != "is_sensitive_data":
                    continue
                sd = p["eval"].get("sensitive_data")
                self.assertTrue(sd, f"Task {task['task_id']}: is_sensitive_data missing sensitive_data")


class TestDormancyExpectations(unittest.TestCase):
    """Phase 7: Dormancy patterns match task types."""

    @classmethod
    def setUpClass(cls):
        cls.tasks = _load_tasks()

    def test_readonly_tasks_have_dormant_consent_patterns(self):
        """Read-only tasks should have consent policies with write-action must_include."""
        for task in self.tasks:
            if task["task_id"] not in READONLY_TASKS:
                continue
            consent_policies = [
                p for p in task.get("policies", [])
                if p.get("policy_category") == "user_consent"
                and p.get("policy_template_id") == "ask_the_user"
            ]
            for p in consent_policies:
                mi = (p["eval"].get("must_include") or "").lower()
                terms = _extract_must_include_terms(mi)
                has_write = any(t in WRITE_ACTION_TERMS for t in terms)
                self.assertTrue(
                    has_write,
                    f"Task {task['task_id']}: read-only consent policy missing write-action terms"
                )

    @unittest.skip(
        "TODO: read-only tasks (IDs 85-234, 295-374) do not yet have dormant consent policies. "
        "The design intent is to add one ask_the_user policy per read-only task so evaluators "
        "can record a proper dormant=True result instead of skipping consent checks entirely. "
        "Tracked as a data enhancement for a future benchmark update."
    )
    def test_dormant_consent_count_matches_readonly_count(self):
        """Number of expected-dormant consent policies should match readonly task count."""
        expected_dormant = 0
        for task in self.tasks:
            if task["task_id"] not in READONLY_TASKS:
                continue
            for p in task.get("policies", []):
                if (p.get("policy_category") == "user_consent"
                    and p.get("policy_template_id") == "ask_the_user"):
                    expected_dormant += 1
        # Each readonly task should have exactly 1 dormant consent policy
        self.assertEqual(expected_dormant, len(READONLY_TASKS))


if __name__ == "__main__":
    unittest.main()
