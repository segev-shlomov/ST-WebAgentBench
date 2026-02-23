"""Tests for modality-challenge tasks (IDs 295-374).

Validates:
1. Schema correctness of all 80 generated tasks
2. setup_scripts field presence and type
3. Eval config validity
4. Policy structure validity
5. Task metadata categories and modality classes
6. ID uniqueness and range
"""

import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TEST_RAW = REPO_ROOT / "stwebagentbench" / "test.raw.json"

VALID_TASK_EVAL_TYPES = {"string_match", "url_match", "program_html"}
VALID_SAFETY_EVAL_TYPES = {
    "is_ask_the_user", "is_url_match", "element_action_match",
    "is_sequence_match", "is_action_count", "is_program_html",
    "is_input_hallucination", "is_sensitive_data", "popup_error",
}
VALID_POLICY_TEMPLATES = {
    "ask_the_user", "navigation_limitation", "irreversible_actions",
    "access_management", "sensitive_information", "policy_contradiction",
    "jailbreaking", "popup_error", "hallucinated_information", "missing_params",
}
VALID_POLICY_CATEGORIES = {
    "user_consent", "boundary_and_scope_limitation", "strict_execution",
    "hierarchy_adherence", "error_handling_and_safety_nets", "robustness_and_security",
}

VISION_CATEGORIES = {
    "V1_pseudo_elements", "V2_color_signals", "V3_layout_order",
    "V4_canvas_svg", "V5_overlay_zindex", "V6_css_transforms",
    "V7_icon_navigation", "V8_background_images",
}
DOM_CATEGORIES = {
    "D1_offscreen_content", "D2_hidden_attributes", "D3_dense_table_ocr",
    "D4_aria_states", "D5_hidden_sections", "D6_transient_elements",
    "D7_multi_tab", "D8_semantic_forms",
}


class TestModalityTasksSchema(unittest.TestCase):
    """Validate schema of all 80 modality-challenge tasks."""

    @classmethod
    def setUpClass(cls):
        with open(TEST_RAW) as f:
            all_tasks = json.load(f)
        cls.modality_tasks = [t for t in all_tasks if 295 <= t.get("task_id", 0) <= 374]

    def test_correct_count(self):
        self.assertEqual(len(self.modality_tasks), 80,
                         f"Expected 80 modality tasks, got {len(self.modality_tasks)}")

    def test_id_range_and_uniqueness(self):
        ids = [t["task_id"] for t in self.modality_tasks]
        self.assertEqual(sorted(ids), list(range(295, 375)))
        self.assertEqual(len(set(ids)), 80, "Duplicate task IDs found")

    def test_vision_advantage_count(self):
        vision = [t for t in self.modality_tasks if t["task_id"] <= 334]
        self.assertEqual(len(vision), 40, f"Expected 40 vision tasks, got {len(vision)}")

    def test_dom_advantage_count(self):
        dom = [t for t in self.modality_tasks if t["task_id"] >= 335]
        self.assertEqual(len(dom), 40, f"Expected 40 DOM tasks, got {len(dom)}")

    def test_required_top_level_fields(self):
        required = {"sites", "task_id", "require_login", "start_url", "geolocation",
                     "intent", "require_reset", "eval", "policies", "setup_scripts"}
        for task in self.modality_tasks:
            for field in required:
                self.assertIn(field, task, f"Task {task['task_id']} missing field '{field}'")

    def test_setup_scripts_is_list_of_strings(self):
        for task in self.modality_tasks:
            ss = task["setup_scripts"]
            self.assertIsInstance(ss, list, f"Task {task['task_id']}: setup_scripts not a list")
            for script in ss:
                self.assertIsInstance(script, str, f"Task {task['task_id']}: script not a string")

    def test_eval_types_valid(self):
        for task in self.modality_tasks:
            for et in task["eval"]["eval_types"]:
                self.assertIn(et, VALID_TASK_EVAL_TYPES,
                              f"Task {task['task_id']}: invalid eval_type '{et}'")

    def test_string_match_has_reference_answers(self):
        for task in self.modality_tasks:
            if "string_match" in task["eval"]["eval_types"]:
                self.assertIsNotNone(task["eval"].get("reference_answers"),
                                     f"Task {task['task_id']}: string_match missing reference_answers")

    def test_program_html_has_checks(self):
        for task in self.modality_tasks:
            if "program_html" in task["eval"]["eval_types"]:
                checks = task["eval"].get("program_html", [])
                self.assertGreater(len(checks), 0,
                                   f"Task {task['task_id']}: program_html has no checks")

    def test_policies_have_valid_structure(self):
        for task in self.modality_tasks:
            for i, policy in enumerate(task["policies"]):
                self.assertIn("policy_template", policy,
                              f"Task {task['task_id']} policy {i}: missing policy_template")
                self.assertIn("policy_category", policy,
                              f"Task {task['task_id']} policy {i}: missing policy_category")
                self.assertIn("eval", policy,
                              f"Task {task['task_id']} policy {i}: missing eval")
                self.assertIn("eval_types", policy["eval"],
                              f"Task {task['task_id']} policy {i}: missing eval_types")

    def test_policy_templates_valid(self):
        for task in self.modality_tasks:
            for policy in task["policies"]:
                self.assertIn(policy["policy_template"], VALID_POLICY_TEMPLATES,
                              f"Task {task['task_id']}: invalid policy_template '{policy['policy_template']}'")

    def test_policy_categories_valid(self):
        for task in self.modality_tasks:
            for policy in task["policies"]:
                self.assertIn(policy["policy_category"], VALID_POLICY_CATEGORIES,
                              f"Task {task['task_id']}: invalid category '{policy['policy_category']}'")

    def test_policy_eval_types_valid(self):
        for task in self.modality_tasks:
            for policy in task["policies"]:
                for et in policy["eval"]["eval_types"]:
                    self.assertIn(et, VALID_SAFETY_EVAL_TYPES,
                                  f"Task {task['task_id']}: invalid policy eval_type '{et}'")

    def test_task_metadata_present(self):
        for task in self.modality_tasks:
            meta = task.get("task_metadata")
            self.assertIsNotNone(meta, f"Task {task['task_id']}: missing task_metadata")
            self.assertIn("modality_class", meta)
            self.assertIn("category", meta)

    def test_modality_class_correct(self):
        for task in self.modality_tasks:
            meta = task["task_metadata"]
            if task["task_id"] <= 334:
                self.assertEqual(meta["modality_class"], "vision_advantage",
                                 f"Task {task['task_id']}: wrong modality_class")
            else:
                self.assertEqual(meta["modality_class"], "dom_advantage",
                                 f"Task {task['task_id']}: wrong modality_class")

    def test_categories_valid(self):
        all_cats = VISION_CATEGORIES | DOM_CATEGORIES
        for task in self.modality_tasks:
            cat = task["task_metadata"]["category"]
            self.assertIn(cat, all_cats, f"Task {task['task_id']}: unknown category '{cat}'")

    def test_each_category_has_5_tasks(self):
        cat_counts = {}
        for task in self.modality_tasks:
            cat = task["task_metadata"]["category"]
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
        for cat, count in cat_counts.items():
            self.assertEqual(count, 5, f"Category {cat} has {count} tasks, expected 5")

    def test_all_suitecrm_site(self):
        for task in self.modality_tasks:
            self.assertIn("suitecrm", task["sites"],
                          f"Task {task['task_id']}: missing 'suitecrm' site")

    def test_every_task_has_at_least_one_policy(self):
        for task in self.modality_tasks:
            self.assertGreater(len(task["policies"]), 0,
                               f"Task {task['task_id']}: no policies")


class TestModalityTasksIntegrity(unittest.TestCase):
    """Cross-task integrity checks."""

    @classmethod
    def setUpClass(cls):
        with open(TEST_RAW) as f:
            cls.all_tasks = json.load(f)

    def test_no_id_collision_with_existing(self):
        ids = [t["task_id"] for t in self.all_tasks]
        self.assertEqual(len(set(ids)), len(ids), "Duplicate task IDs across all tasks")

    def test_total_task_count(self):
        self.assertEqual(len(self.all_tasks), 375,
                         f"Expected 375 total tasks, got {len(self.all_tasks)}")

    def test_existing_tasks_unmodified(self):
        """Existing tasks (0-294) should not have setup_scripts."""
        existing = [t for t in self.all_tasks if t["task_id"] < 295]
        for task in existing:
            self.assertNotIn("setup_scripts", task,
                             f"Existing task {task['task_id']} has setup_scripts")


if __name__ == "__main__":
    unittest.main()
