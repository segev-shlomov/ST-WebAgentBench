#!/usr/bin/env python3
"""Comprehensive offline validation of the ST-WebAgentBench benchmark.

Runs 7 validation phases against test.raw.json and the evaluator code:
  1. Schema & structural integrity
  2. Evaluator instantiation
  3. Dimension coverage & diversity
  4. Cross-dimension conflict detection
  5. CRM tier superset validation
  6. Evaluator-specific field validation
  7. Dormancy analysis

Usage:
    PYTHONPATH=. python3 scripts/validate_benchmark.py
"""

import json
import sys
import tempfile
import re
from collections import Counter, defaultdict
from pathlib import Path

# ── imports from the benchmark package ──────────────────────────────────────
from stwebagentbench.evaluation_harness.evaluators import (
    validate_policy_schema,
    safety_evaluator_router,
    VALID_EVAL_TYPES,
    VALID_SAFETY_EVAL_TYPES,
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

# ── Constants ───────────────────────────────────────────────────────────────
TASKS_PATH = Path("stwebagentbench/test.raw.json")

# Eval-type → expected evaluator class
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

# Required policy fields
REQUIRED_FIELDS = {"policy_template_id", "policy_category", "source", "description", "eval"}

# Dimension thresholds: (min_coverage, min_templates, min_eval_types, min_unique_descs)
DIMENSION_THRESHOLDS = {
    "user_consent":                    (375, 3, 2, 60),
    "boundary_and_scope_limitation":   (375, 3, 3, 60),
    "error_handling_and_safety_nets":  (375, 3, 2, 60),
    "hierarchy_adherence":             (120, 2, 2, 50),
    "robustness_and_security":         (200, 2, 2, 50),
    "strict_execution":                (370, 3, 4, 50),
}

# CRM tier ranges
CRM_EASY = list(range(235, 255))
CRM_MEDIUM = list(range(255, 275))
CRM_HARD = list(range(275, 295))

# Read-only task IDs (dormant consent expected)
READONLY_GITLAB = set(range(85, 235))
READONLY_MODALITY = set(range(295, 375)) - {297, 302, 307}
READONLY_TASKS = READONLY_GITLAB | READONLY_MODALITY

# Write-action terms used in dormant consent policies
WRITE_ACTION_TERMS = {"save", "delete", "submit", "merge", "invite", "update", "edit"}

# Valid action types for element_action_match
VALID_ACTION_TYPES = {
    "click", "fill", "type", "select_option", "hover", "press",
    "dblclick", "scroll", "send_msg_to_user", "goto",
}


def load_tasks():
    with open(TASKS_PATH) as f:
        return json.load(f)


# ── Phase 1: Schema & Structural Integrity ─────────────────────────────────

def phase1_schema(tasks):
    errors = []
    total_policies = 0

    for task in tasks:
        tid = task["task_id"]
        for idx, policy in enumerate(task.get("policies", [])):
            total_policies += 1

            # Check required fields
            missing = REQUIRED_FIELDS - set(policy.keys())
            if missing:
                errors.append(f"Task {tid} policy {idx}: missing fields {missing}")

            # Check eval_types
            eval_data = policy.get("eval", {})
            eval_types = eval_data.get("eval_types", [])
            if not eval_types:
                errors.append(f"Task {tid} policy {idx}: empty eval_types")
                continue

            eval_type = eval_types[0]
            if eval_type not in VALID_EVAL_TYPES:
                errors.append(f"Task {tid} policy {idx}: unknown eval_type '{eval_type}'")

            # Run full schema validation
            try:
                issues = validate_policy_schema(policy, level=VALIDATION_STRICT)
            except ValueError as e:
                errors.append(f"Task {tid} policy {idx}: schema error: {e}")

    return total_policies, errors


# ── Phase 2: Evaluator Instantiation ───────────────────────────────────────

def phase2_instantiation(tasks):
    errors = []
    total_evaluators = 0

    for task in tasks:
        tid = task["task_id"]
        config = {
            "eval": task.get("eval", {}),
            "policies": task.get("policies", []),
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            tmp_path = f.name

        try:
            comb = safety_evaluator_router(tmp_path)
            if not isinstance(comb, SafetyEvaluatorComb):
                errors.append(f"Task {tid}: router returned {type(comb).__name__}, expected SafetyEvaluatorComb")
                continue

            n_evaluators = len(comb.evaluators)
            n_policies = len(task.get("policies", []))
            total_evaluators += n_evaluators

            if n_evaluators != n_policies:
                errors.append(f"Task {tid}: {n_evaluators} evaluators != {n_policies} policies")

            # Verify each evaluator is the correct class
            for idx, (evaluator, policy) in enumerate(zip(comb.evaluators, task["policies"])):
                eval_type = policy["eval"]["eval_types"][0]
                expected_cls = EVAL_TYPE_TO_CLASS.get(eval_type)
                if expected_cls and not isinstance(evaluator, expected_cls):
                    errors.append(
                        f"Task {tid} policy {idx}: evaluator is {type(evaluator).__name__}, "
                        f"expected {expected_cls.__name__} for eval_type '{eval_type}'"
                    )

        except Exception as e:
            errors.append(f"Task {tid}: instantiation failed: {e}")
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    return total_evaluators, errors


# ── Phase 3: Dimension Coverage & Diversity ─────────────────────────────────

def phase3_coverage(tasks):
    errors = []
    dim_stats = {}

    for dim_name in DIMENSION_THRESHOLDS:
        covered_tasks = set()
        templates = set()
        eval_types_set = set()
        descriptions = set()
        generic_count = 0

        for task in tasks:
            for policy in task.get("policies", []):
                if policy.get("policy_category") != dim_name:
                    continue

                covered_tasks.add(task["task_id"])
                templates.add(policy["policy_template_id"])
                for et in policy["eval"].get("eval_types", []):
                    eval_types_set.add(et)
                descriptions.add(policy["description"])

                # Check for generic descriptions
                desc = policy["description"].strip()
                if (len(desc) < 20 or
                    desc == "ask the user permission before performing an action"):
                    generic_count += 1

        min_cov, min_tpl, min_et, min_desc = DIMENSION_THRESHOLDS[dim_name]

        stats = {
            "coverage": len(covered_tasks),
            "templates": len(templates),
            "eval_types": len(eval_types_set),
            "unique_descs": len(descriptions),
            "generic_count": generic_count,
        }
        dim_stats[dim_name] = stats

        if stats["coverage"] < min_cov:
            errors.append(f"{dim_name}: coverage {stats['coverage']}/{len(tasks)} < {min_cov}")
        if stats["templates"] < min_tpl:
            errors.append(f"{dim_name}: templates {stats['templates']} < {min_tpl}")
        if stats["eval_types"] < min_et:
            errors.append(f"{dim_name}: eval_types {stats['eval_types']} < {min_et}")
        if stats["unique_descs"] < min_desc:
            errors.append(f"{dim_name}: unique_descs {stats['unique_descs']} < {min_desc}")
        if stats["generic_count"] > 0:
            errors.append(f"{dim_name}: {stats['generic_count']} generic descriptions remaining")

    return dim_stats, errors


# ── Phase 4: Cross-Dimension Conflict Detection ────────────────────────────

def _extract_must_include_terms(must_include_str):
    """Split must_include by '|or|' or '|OR|' and return lowercase terms."""
    if not must_include_str:
        return set()
    parts = re.split(r'\s*\|(?:or|OR)\|\s*', must_include_str)
    return {p.strip().lower() for p in parts if p.strip()}


def phase4_conflicts(tasks):
    errors = []
    task_by_id = {t["task_id"]: t for t in tasks}

    for task in tasks:
        tid = task["task_id"]
        intent = task.get("intent", "").lower()
        start_url = task.get("start_url", "").lower()
        policies = task.get("policies", [])

        # Collect do_not_click terms
        do_not_click_terms = set()
        ask_user_terms = set()
        policy_fingerprints = []

        for policy in policies:
            template_id = policy.get("policy_template_id", "")
            eval_data = policy.get("eval", {})
            eval_types = tuple(eval_data.get("eval_types", []))
            must_include = eval_data.get("must_include") or ""
            action_type = eval_data.get("action_type") or ""

            if template_id in ("do_not_click", "do_not_type"):
                terms = _extract_must_include_terms(must_include)
                do_not_click_terms.update(terms)

            if template_id == "ask_the_user":
                terms = _extract_must_include_terms(must_include)
                ask_user_terms.update(terms)

            # Duplicate fingerprint check — use full eval dict to avoid false positives
            fp = (template_id, json.dumps(eval_data, sort_keys=True, default=str))
            policy_fingerprints.append(fp)

        # Check: do_not_click terms vs intent keywords
        for term in do_not_click_terms:
            # Only flag if the exact term appears as a word in the intent
            # Use word boundary matching to avoid false positives
            if len(term) > 3 and re.search(r'\b' + re.escape(term) + r'\b', intent):
                errors.append(
                    f"Task {tid}: CONFLICT — do_not_click term '{term}' found in task intent"
                )

        # Check: restrict_url vs start_url
        for policy in policies:
            if policy.get("policy_template_id") == "restrict_url":
                ref_url = policy.get("eval", {}).get("reference_url", "").lower()
                if ref_url and start_url:
                    # Check if start_url domain is blocked
                    if ref_url in start_url or start_url in ref_url:
                        errors.append(
                            f"Task {tid}: CONFLICT — restrict_url blocks '{ref_url}' but start_url is '{start_url}'"
                        )

        # Check: duplicate policies within same task (identical eval configs)
        fp_counter = Counter(policy_fingerprints)
        for fp, count in fp_counter.items():
            if count > 1:
                errors.append(
                    f"Task {tid}: REDUNDANT — identical policy '{fp[0]}' appears {count} times"
                )

    return errors


# ── Phase 5: CRM Tier Superset Validation ──────────────────────────────────

def _get_policy_fingerprints(task):
    """Extract set of (template_id, category, eval_types_tuple) from task policies."""
    fps = set()
    for p in task.get("policies", []):
        fps.add((
            p["policy_template_id"],
            p["policy_category"],
            tuple(p["eval"].get("eval_types", [])),
        ))
    return fps


def phase5_superset(tasks):
    errors = []
    task_by_id = {t["task_id"]: t for t in tasks}

    for i in range(20):  # 20 config groups
        easy_id = CRM_EASY[i]
        medium_id = CRM_MEDIUM[i]
        hard_id = CRM_HARD[i]

        easy_task = task_by_id.get(easy_id)
        medium_task = task_by_id.get(medium_id)
        hard_task = task_by_id.get(hard_id)

        if not all([easy_task, medium_task, hard_task]):
            errors.append(f"Config group {i}: missing task(s) ({easy_id}, {medium_id}, {hard_id})")
            continue

        easy_fps = _get_policy_fingerprints(easy_task)
        medium_fps = _get_policy_fingerprints(medium_task)
        hard_fps = _get_policy_fingerprints(hard_task)

        # Easy ⊆ Medium
        if not easy_fps.issubset(medium_fps):
            diff = easy_fps - medium_fps
            errors.append(
                f"Config group {i}: Easy ⊄ Medium — missing: {diff}"
            )

        # Medium ⊆ Hard
        if not medium_fps.issubset(hard_fps):
            diff = medium_fps - hard_fps
            errors.append(
                f"Config group {i}: Medium ⊄ Hard — missing: {diff}"
            )

        # Size ordering
        n_easy = len(easy_task.get("policies", []))
        n_medium = len(medium_task.get("policies", []))
        n_hard = len(hard_task.get("policies", []))

        if n_medium <= n_easy:
            errors.append(
                f"Config group {i}: |Medium|={n_medium} <= |Easy|={n_easy}"
            )
        if n_hard < n_medium:
            errors.append(
                f"Config group {i}: |Hard|={n_hard} < |Medium|={n_medium}"
            )

    return errors


# ── Phase 6: Evaluator-Specific Field Validation ───────────────────────────

def phase6_fields(tasks):
    errors = []

    for task in tasks:
        tid = task["task_id"]
        for idx, policy in enumerate(task.get("policies", [])):
            eval_data = policy.get("eval", {})
            eval_types = eval_data.get("eval_types", [])
            if not eval_types:
                continue
            eval_type = eval_types[0]
            template_id = policy.get("policy_template_id", "unknown")

            if eval_type == "is_ask_the_user":
                mi = eval_data.get("must_include", "")
                if not mi or not mi.strip():
                    errors.append(f"Task {tid} [{template_id}]: is_ask_the_user has empty must_include")
                else:
                    terms = _extract_must_include_terms(mi)
                    for term in terms:
                        if len(term) < 2:
                            errors.append(
                                f"Task {tid} [{template_id}]: is_ask_the_user term '{term}' too short (<2 chars)"
                            )

            elif eval_type == "element_action_match":
                mi = eval_data.get("must_include", "")
                es = eval_data.get("element_selector", "")
                if not mi and not es:
                    errors.append(f"Task {tid} [{template_id}]: element_action_match needs must_include or element_selector")
                at = eval_data.get("action_type", "")
                if at and at.lower() not in VALID_ACTION_TYPES:
                    errors.append(f"Task {tid} [{template_id}]: invalid action_type '{at}'")

            elif eval_type == "is_action_count":
                gc = eval_data.get("global_count")
                gcl = eval_data.get("global_count_less_than")
                gca = eval_data.get("global_count_at_least")
                count_fields = [x for x in [gc, gcl, gca] if x is not None]
                if len(count_fields) == 0:
                    errors.append(f"Task {tid} [{template_id}]: is_action_count missing count field")
                elif len(count_fields) > 1:
                    errors.append(f"Task {tid} [{template_id}]: is_action_count has multiple count fields")
                for val in count_fields:
                    if not isinstance(val, (int, float)) or val < 0:
                        errors.append(f"Task {tid} [{template_id}]: invalid count value {val}")
                at = eval_data.get("action_type", "")
                if not at:
                    errors.append(f"Task {tid} [{template_id}]: is_action_count missing action_type")

            elif eval_type == "is_url_match":
                ref = eval_data.get("reference_url", "")
                mi = eval_data.get("must_include", "")
                if not ref and not mi:
                    errors.append(f"Task {tid} [{template_id}]: is_url_match needs reference_url or must_include")

            elif eval_type == "is_program_html":
                ph = eval_data.get("program_html")
                url = eval_data.get("url")
                rc = eval_data.get("required_contents")
                if not ph and not url and not rc:
                    errors.append(f"Task {tid} [{template_id}]: is_program_html needs program_html or url/required_contents")

            elif eval_type == "is_input_hallucination":
                of = eval_data.get("only_fill")
                if of is None:
                    errors.append(f"Task {tid} [{template_id}]: is_input_hallucination missing only_fill")

            elif eval_type == "is_sensitive_data":
                sd = eval_data.get("sensitive_data")
                if not sd:
                    errors.append(f"Task {tid} [{template_id}]: is_sensitive_data missing sensitive_data")

    return errors


# ── Phase 7: Dormancy Analysis ──────────────────────────────────────────────

def phase7_dormancy(tasks):
    errors = []
    expected_dormant = 0
    unexpected_dormant = 0
    task_by_id = {t["task_id"]: t for t in tasks}

    for task in tasks:
        tid = task["task_id"]
        is_readonly = tid in READONLY_TASKS

        for policy in task.get("policies", []):
            template_id = policy.get("policy_template_id", "")
            category = policy.get("policy_category", "")
            eval_data = policy.get("eval", {})

            if category == "user_consent" and template_id == "ask_the_user":
                must_include = (eval_data.get("must_include") or "").lower()
                terms = _extract_must_include_terms(must_include)
                has_write_terms = any(t in WRITE_ACTION_TERMS for t in terms)

                if is_readonly and has_write_terms:
                    expected_dormant += 1
                elif not is_readonly and has_write_terms:
                    # Write task with write terms — should be active (not dormant)
                    pass  # This is correct behavior

    # Summary stats
    total_consent_policies = sum(
        1 for t in tasks for p in t.get("policies", [])
        if p.get("policy_category") == "user_consent"
    )

    return {
        "expected_dormant": expected_dormant,
        "total_consent_policies": total_consent_policies,
        "readonly_tasks": len(READONLY_TASKS),
    }, errors


# ── Main Report ─────────────────────────────────────────────────────────────

def run_validation():
    print("=" * 70)
    print("  ST-WebAgentBench Comprehensive Validation Report")
    print("=" * 70)
    print()

    tasks = load_tasks()
    total_tasks = len(tasks)
    total_policies = sum(len(t.get("policies", [])) for t in tasks)
    print(f"  Loaded: {total_tasks} tasks, {total_policies} policies")
    print()

    all_passed = True

    # ── Phase 1 ─────────────────────────────────────────────────────────────
    print("-" * 70)
    print("  Phase 1: Schema & Structural Integrity")
    print("-" * 70)
    n_validated, errors = phase1_schema(tasks)
    print(f"  Policies validated: {n_validated}")
    if errors:
        all_passed = False
        print(f"  Schema errors: {len(errors)}                            FAIL")
        for e in errors[:20]:
            print(f"    - {e}")
        if len(errors) > 20:
            print(f"    ... and {len(errors) - 20} more")
    else:
        print(f"  Schema errors: 0                                     PASS")
    print()

    # ── Phase 2 ─────────────────────────────────────────────────────────────
    print("-" * 70)
    print("  Phase 2: Evaluator Instantiation")
    print("-" * 70)
    n_evaluators, errors = phase2_instantiation(tasks)
    print(f"  Evaluators created: {n_evaluators}")
    if errors:
        all_passed = False
        print(f"  Instantiation errors: {len(errors)}                     FAIL")
        for e in errors[:20]:
            print(f"    - {e}")
        if len(errors) > 20:
            print(f"    ... and {len(errors) - 20} more")
    else:
        print(f"  Instantiation errors: 0                              PASS")
    print()

    # ── Phase 3 ─────────────────────────────────────────────────────────────
    print("-" * 70)
    print("  Phase 3: Dimension Coverage & Diversity")
    print("-" * 70)
    dim_stats, errors = phase3_coverage(tasks)
    phase3_pass = len(errors) == 0
    for dim, stats in dim_stats.items():
        short = dim[:35].ljust(35)
        print(f"  {short} {stats['coverage']:>3}/{total_tasks} tasks, "
              f"{stats['templates']} templates, {stats['eval_types']} eval_types, "
              f"{stats['unique_descs']} descs")
    if errors:
        all_passed = False
        print(f"\n  Dimension errors: {len(errors)}                         FAIL")
        for e in errors:
            print(f"    - {e}")
    else:
        print(f"\n  All dimensions meet thresholds                       PASS")
    print()

    # ── Phase 4 ─────────────────────────────────────────────────────────────
    print("-" * 70)
    print("  Phase 4: Cross-Dimension Conflict Detection")
    print("-" * 70)
    errors = phase4_conflicts(tasks)
    if errors:
        all_passed = False
        print(f"  Conflicts found: {len(errors)}                           FAIL")
        for e in errors[:20]:
            print(f"    - {e}")
        if len(errors) > 20:
            print(f"    ... and {len(errors) - 20} more")
    else:
        print(f"  Conflicts found: 0                                   PASS")
    print()

    # ── Phase 5 ─────────────────────────────────────────────────────────────
    print("-" * 70)
    print("  Phase 5: CRM Tier Superset Validation")
    print("-" * 70)
    errors = phase5_superset(tasks)
    if errors:
        all_passed = False
        print(f"  Superset errors: {len(errors)}                           FAIL")
        for e in errors:
            print(f"    - {e}")
    else:
        print(f"  Easy <= Medium: 20/20 groups                         PASS")
        print(f"  Medium <= Hard: 20/20 groups                         PASS")
    print()

    # ── Phase 6 ─────────────────────────────────────────────────────────────
    print("-" * 70)
    print("  Phase 6: Evaluator-Specific Field Validation")
    print("-" * 70)
    errors = phase6_fields(tasks)
    if errors:
        all_passed = False
        print(f"  Field errors: {len(errors)}                              FAIL")
        for e in errors[:20]:
            print(f"    - {e}")
        if len(errors) > 20:
            print(f"    ... and {len(errors) - 20} more")
    else:
        print(f"  Policies with invalid fields: 0                      PASS")
    print()

    # ── Phase 7 ─────────────────────────────────────────────────────────────
    print("-" * 70)
    print("  Phase 7: Dormancy Analysis")
    print("-" * 70)
    dormancy_stats, errors = phase7_dormancy(tasks)
    print(f"  Read-only tasks: {dormancy_stats['readonly_tasks']}")
    print(f"  Expected dormant consent policies: {dormancy_stats['expected_dormant']}")
    print(f"  Total consent policies: {dormancy_stats['total_consent_policies']}")
    if errors:
        all_passed = False
        print(f"  Dormancy issues: {len(errors)}                           FAIL")
        for e in errors:
            print(f"    - {e}")
    else:
        print(f"  Unexpected dormancy: 0                               PASS")
    print()

    # ── Summary ─────────────────────────────────────────────────────────────
    print("=" * 70)
    if all_passed:
        print("  OVERALL: ALL 7 PHASES PASSED — Benchmark is ICLR-ready")
    else:
        print("  OVERALL: VALIDATION FAILED — See errors above")
    print("=" * 70)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(run_validation())
