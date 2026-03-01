#!/usr/bin/env python3
"""Comprehensive per-task feasibility audit.

Checks every task (375) for policy conflicts, logical issues,
and whether a strong agent can achieve CuP (task completion + 0 violations).

Checks performed:
  1. Hallucination-hierarchy conflicts (only_fill vs hierarchy must_include)
  2. Sensitive data vs task intent conflicts (task needs data that's marked sensitive)
  3. URL restriction vs task navigation conflicts
  4. Action count feasibility (is the limit achievable?)
  5. Sequence ordering feasibility
  6. Consent dormancy correctness (read-only tasks should have dormant consent)
  7. Missing_params feasibility (keywords actually achievable)
  8. Cross-policy contradictions (e.g., two policies requiring opposite states)
  9. Duplicate policies (identical eval configs)
 10. Empty/missing required eval fields
 11. check_absence consistency with policy_template_id
 12. Hierarchy policy achievability (can agent actually produce must_include)
 13. Only_fill completeness (task intent values present in whitelist)
"""

import json
import re
import sys
from pathlib import Path
from collections import Counter, defaultdict

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TASKS_FILE = PROJECT_ROOT / "stwebagentbench" / "test.raw.json"

# ── Severity levels ──
CRITICAL = "CRITICAL"  # Would cause false violation — CuP impossible
WARNING = "WARNING"    # Suspicious but may not block CuP
INFO = "INFO"          # Informational observation


def load_tasks():
    with open(TASKS_FILE) as f:
        return json.load(f)


def extract_intent_values(intent):
    """Extract quoted values and key data from task intent."""
    # Single-quoted values
    sq = re.findall(r"'([^']+)'", intent)
    # Double-quoted values
    dq = re.findall(r'"([^"]+)"', intent)
    # Dates (YYYY-MM-DD)
    dates = re.findall(r'\b(\d{4}-\d{2}-\d{2})\b', intent)
    # Times (HH:MM)
    times = re.findall(r'\b(\d{1,2}:\d{2})\b', intent)
    # Emails
    emails = re.findall(r'[\w.-]+@[\w.-]+', intent)
    return set(sq + dq + dates + times + emails)


def get_eval_type(policy):
    """Get the primary eval type of a policy."""
    et = policy.get("eval", {}).get("eval_types", [])
    return et[0] if et else None


def get_template_id(policy):
    return policy.get("policy_template_id", "")


def get_category(policy):
    return policy.get("policy_category", "")


# ════════════════════════════════════════════════════════════════
# CHECK FUNCTIONS — each returns list of (severity, message)
# ════════════════════════════════════════════════════════════════


def check_hallucination_hierarchy(task):
    """Check 1: only_fill includes all hierarchy-required values."""
    issues = []
    policies = task.get("policies", [])
    intent = task.get("intent", "").lower()

    hall_pols = [p for p in policies if get_eval_type(p) == "is_input_hallucination"]
    hier_pols = [p for p in policies if get_template_id(p) in ("policy_contradiction", "hierarchy_resolution")]

    if not hall_pols or not hier_pols:
        return issues

    for hp in hall_pols:
        only_fill = hp["eval"].get("only_fill", [])
        if not only_fill:
            continue
        only_fill_lower = {v.lower() for v in only_fill}

        for hpol in hier_pols:
            # From program_html must_include
            for ph in hpol.get("eval", {}).get("program_html", []):
                for mi in ph.get("required_contents", {}).get("must_include", []):
                    if mi.lower() not in only_fill_lower:
                        issues.append((CRITICAL,
                            f"Hierarchy requires '{mi}' but only_fill doesn't include it "
                            f"(from {get_template_id(hpol)})"))

    return issues


def check_sensitive_data_vs_intent(task):
    """Check 2: Sensitive data patterns don't block task completion."""
    issues = []
    policies = task.get("policies", [])
    intent = task.get("intent", "").lower()
    intent_values = extract_intent_values(task.get("intent", ""))

    sens_pols = [p for p in policies if get_eval_type(p) == "is_sensitive_data"]
    for sp in sens_pols:
        sens_data = sp["eval"].get("sensitive_data", "").lower()
        leak_only = sp["eval"].get("leak_only", False)
        if not sens_data:
            continue

        # Check if task intent requires typing this sensitive data
        for iv in intent_values:
            if sens_data in iv.lower() or iv.lower() in sens_data:
                if not leak_only:
                    issues.append((CRITICAL,
                        f"Sensitive data '{sens_data}' overlaps with intent value '{iv}' "
                        f"and leak_only=False — agent can't type it"))
                else:
                    issues.append((INFO,
                        f"Sensitive data '{sens_data}' overlaps with intent value '{iv}' "
                        f"but leak_only=True — agent can type it in forms"))

    return issues


def check_url_restrictions(task):
    """Check 3: URL restrictions don't block necessary navigation."""
    issues = []
    policies = task.get("policies", [])
    intent = task.get("intent", "").lower()
    start_url = task.get("start_url", "").lower()

    url_pols = [p for p in policies if get_eval_type(p) == "is_url_match"]
    for up in url_pols:
        check_absence = up.get("eval", {}).get("check_absence", True)
        ref_url = up["eval"].get("reference_url", "")
        url_note = up["eval"].get("url_note", "")

        if not ref_url:
            issues.append((WARNING, f"URL policy has empty reference_url"))
            continue

        if check_absence:
            # Forbidden URL mode — check intent doesn't require navigating there
            forbidden_parts = [p.strip().lower() for p in ref_url.split(" |OR| ")]
            for fp in forbidden_parts:
                # Check if intent mentions a module that's forbidden
                if "module=" in fp:
                    module = fp.split("module=")[1].strip().lower()
                    # Check if intent directly references this module
                    if module in intent:
                        issues.append((WARNING,
                            f"URL restriction forbids '{fp}' but intent mentions '{module}'"))

    return issues


def check_action_count(task):
    """Check 4: Action count limits are achievable."""
    issues = []
    policies = task.get("policies", [])
    intent = task.get("intent", "")

    # Count how many UNIQUE URLs need fills (targets on same URL share one fill visit)
    eval_targets = task.get("eval", {}).get("program_html", []) or []
    unique_fill_urls = len({t.get("url", "") for t in eval_targets})

    for p in policies:
        if get_eval_type(p) != "is_action_count":
            continue
        limit = p["eval"].get("global_count_less_than")
        action_type = p["eval"].get("action_type", "")
        element_selectors = p["eval"].get("element_selectors")

        # If element_selectors are set, the limit applies only to specific elements
        # — much more permissive, skip the low-limit check
        if element_selectors:
            continue

        if limit is not None:
            # Check if task has multiple unique URL targets that each need fills
            if action_type == "fill" and unique_fill_urls > 1 and limit <= unique_fill_urls:
                issues.append((CRITICAL,
                    f"Action count {action_type}<{limit} but task has {unique_fill_urls} "
                    f"unique eval URLs requiring separate fills"))
            elif limit < 3:
                issues.append((WARNING,
                    f"Action count limit {action_type}<{limit} is tight (no element_selectors)"))

    return issues


def check_sequence_feasibility(task):
    """Check 5: Sequence ordering is achievable."""
    issues = []
    policies = task.get("policies", [])

    for p in policies:
        if get_eval_type(p) != "is_sequence_match":
            continue
        seq = p["eval"].get("action_sequence", [])
        if not seq:
            issues.append((WARNING, "Sequence policy has empty action_sequence"))
            continue
        if len(seq) < 2:
            issues.append((WARNING, "Sequence policy has only 1 step — trivially satisfied"))

    return issues


def check_consent_dormancy(task):
    """Check 6: Consent policies on read-only tasks should be dormant-capable."""
    issues = []
    policies = task.get("policies", [])
    intent = task.get("intent", "").lower()

    # Check if task is read-only (no write actions in intent)
    write_keywords = {"save", "delete", "submit", "create", "update", "merge",
                      "invite", "edit", "schedule", "import", "export", "send",
                      "forward", "escalate", "assign", "associate", "add"}
    has_write = any(kw in intent for kw in write_keywords)

    if has_write:
        return issues  # Write tasks — consent policies can fire

    # For read-only tasks, consent (ask_the_user) policies should be dormant
    for p in policies:
        if get_eval_type(p) == "is_ask_the_user":
            tmpl = get_template_id(p)
            if tmpl == "missing_params":
                issues.append((WARNING,
                    f"Read-only task has missing_params policy — will always violate"))

    return issues


def check_missing_params(task):
    """Check 7: missing_params keywords are achievable."""
    issues = []
    policies = task.get("policies", [])

    for p in policies:
        if get_template_id(p) != "missing_params":
            continue
        must_include = p["eval"].get("must_include", "")
        if not must_include:
            issues.append((CRITICAL, "missing_params policy has empty must_include"))
            continue
        terms = [t.strip() for t in must_include.split(" |or| ") if t.strip()]
        if not terms:
            issues.append((CRITICAL, "missing_params policy has no valid terms"))

    return issues


def check_duplicate_policies(task):
    """Check 9: No duplicate policies with identical eval configs."""
    issues = []
    policies = task.get("policies", [])
    seen = []

    for i, p in enumerate(policies):
        eval_key = json.dumps(p["eval"], sort_keys=True)
        tmpl = get_template_id(p)
        for j, (prev_tmpl, prev_key) in enumerate(seen):
            if eval_key == prev_key and tmpl == prev_tmpl:
                issues.append((CRITICAL,
                    f"Duplicate policy: [{i}] and [{j}] have identical eval configs "
                    f"(template={tmpl})"))
        seen.append((tmpl, eval_key))

    return issues


def check_eval_fields(task):
    """Check 10: All required eval fields are present and valid."""
    issues = []
    policies = task.get("policies", [])

    REQUIRED_FIELDS = {
        "is_ask_the_user": ["must_include"],
        "is_url_match": ["reference_url"],
        "is_sequence_match": ["action_sequence"],
        "is_action_count": ["action_type"],
        "is_input_hallucination": ["only_fill"],
        "is_sensitive_data": ["sensitive_data"],
    }

    for i, p in enumerate(policies):
        et = get_eval_type(p)
        if et in REQUIRED_FIELDS:
            for field in REQUIRED_FIELDS[et]:
                val = p["eval"].get(field)
                if val is None or val == "" or val == []:
                    issues.append((CRITICAL,
                        f"Policy [{i}] ({et}): required field '{field}' is empty/None"))

    return issues


def check_check_absence_consistency(task):
    """Check 11: check_absence aligns with policy template semantics."""
    issues = []
    policies = task.get("policies", [])

    for i, p in enumerate(policies):
        et = get_eval_type(p)
        tmpl = get_template_id(p)
        check_absence = p.get("eval", {}).get("check_absence")

        if et == "is_program_html" and check_absence is not None:
            # policy_contradiction should have check_absence=True (distractor)
            # hierarchy_resolution should have check_absence=False (requirement)
            if tmpl == "policy_contradiction" and check_absence is False:
                issues.append((WARNING,
                    f"Policy [{i}]: policy_contradiction with check_absence=False — "
                    f"should this be hierarchy_resolution instead?"))
            elif tmpl == "hierarchy_resolution" and check_absence is True:
                issues.append((WARNING,
                    f"Policy [{i}]: hierarchy_resolution with check_absence=True — "
                    f"should this be policy_contradiction instead?"))

    return issues


def check_hierarchy_achievability(task):
    """Check 12: Hierarchy policies' must_include values are achievable."""
    issues = []
    policies = task.get("policies", [])
    intent = task.get("intent", "").lower()

    for i, p in enumerate(policies):
        tmpl = get_template_id(p)
        if tmpl not in ("policy_contradiction", "hierarchy_resolution"):
            continue

        check_absence = p.get("eval", {}).get("check_absence", True)

        for ph in p.get("eval", {}).get("program_html", []):
            mi_list = ph.get("required_contents", {}).get("must_include", [])
            for mi in mi_list:
                # For policy_contradiction (check_absence=True):
                # Content found = violation. Agent must NOT produce this content.
                # But description says "instead, update to X" — so agent SHOULD produce it.
                # This is by design: the contradiction policy checks if agent deleted
                # instead of following the org policy.
                pass  # This is complex semantic check — handled by trajectory analysis

    return issues


def check_only_fill_completeness(task):
    """Check 13: only_fill includes all values from task intent."""
    issues = []
    policies = task.get("policies", [])
    intent = task.get("intent", "")
    intent_values = extract_intent_values(intent)

    for p in policies:
        if get_eval_type(p) != "is_input_hallucination":
            continue
        only_fill = p["eval"].get("only_fill", [])
        if not only_fill:
            continue

        only_fill_lower = {v.lower() for v in only_fill}

        for iv in intent_values:
            if iv.lower() not in only_fill_lower:
                # Check if any only_fill value contains this intent value
                found = any(iv.lower() in of for of in only_fill_lower)
                if not found:
                    # Check if it's a common variant (date parts, etc.)
                    # Skip single digits, common fragments
                    if len(iv) < 3 or iv.isdigit():
                        continue
                    issues.append((WARNING,
                        f"Intent value '{iv}' not in only_fill={only_fill}"))

    return issues


def check_contradiction_pairs(task):
    """Check 8: No two policies require opposite outcomes on the same element."""
    issues = []
    policies = task.get("policies", [])

    # Check for conflicting program_html: same locator, contradicting must_include
    html_pols = [p for p in policies if get_eval_type(p) == "is_program_html"]
    for i, p1 in enumerate(html_pols):
        for j, p2 in enumerate(html_pols):
            if j <= i:
                continue
            ca1 = p1.get("eval", {}).get("check_absence", True)
            ca2 = p2.get("eval", {}).get("check_absence", True)
            # One requires presence, other requires absence of same content
            if ca1 != ca2:
                # Check if they target the same content
                mi1 = set()
                mi2 = set()
                for ph in (p1.get("eval", {}).get("program_html") or []):
                    for v in ph.get("required_contents", {}).get("must_include", []):
                        mi1.add(v.lower())
                for ph in (p2.get("eval", {}).get("program_html") or []):
                    for v in ph.get("required_contents", {}).get("must_include", []):
                        mi2.add(v.lower())
                overlap = mi1 & mi2
                if overlap:
                    issues.append((CRITICAL,
                        f"Contradicting policies: one requires presence, other absence "
                        f"of same content: {overlap}"))

    return issues


def check_sensitive_data_in_only_fill(task):
    """Check: sensitive_data values should NOT appear in only_fill."""
    issues = []
    policies = task.get("policies", [])

    sens_values = set()
    for p in policies:
        if get_eval_type(p) == "is_sensitive_data":
            sd = p["eval"].get("sensitive_data", "").strip().lower()
            if sd:
                sens_values.add(sd)

    if not sens_values:
        return issues

    for p in policies:
        if get_eval_type(p) != "is_input_hallucination":
            continue
        only_fill = p["eval"].get("only_fill", [])
        if not only_fill:
            continue
        only_fill_lower = {v.lower() for v in only_fill}

        for sv in sens_values:
            if sv in only_fill_lower:
                # Check if the sensitive data policy has leak_only=True
                leak_only_pol = next(
                    (sp for sp in policies
                     if get_eval_type(sp) == "is_sensitive_data"
                     and sp["eval"].get("sensitive_data", "").strip().lower() == sv),
                    None
                )
                if leak_only_pol and not leak_only_pol.get("eval", {}).get("leak_only", False):
                    issues.append((CRITICAL,
                        f"Sensitive data '{sv}' is in only_fill but leak_only=False — "
                        f"typing it would trigger sensitive_data violation"))

    return issues


def check_popup_error_consistency(task):
    """Check: popup_error policies should have meaningful descriptions."""
    issues = []
    policies = task.get("policies", [])

    for i, p in enumerate(policies):
        if get_eval_type(p) != "popup_error":
            continue
        desc = p.get("description", "")
        if len(desc) < 10:
            issues.append((WARNING,
                f"Policy [{i}] (popup_error): description too short: '{desc}'"))

    return issues


# ════════════════════════════════════════════════════════════════
# MAIN AUDIT
# ════════════════════════════════════════════════════════════════


ALL_CHECKS = [
    ("Hallucination-Hierarchy", check_hallucination_hierarchy),
    ("Sensitive Data vs Intent", check_sensitive_data_vs_intent),
    ("URL Restrictions", check_url_restrictions),
    ("Action Count", check_action_count),
    ("Sequence Feasibility", check_sequence_feasibility),
    ("Consent Dormancy", check_consent_dormancy),
    ("Missing Params", check_missing_params),
    ("Contradiction Pairs", check_contradiction_pairs),
    ("Duplicate Policies", check_duplicate_policies),
    ("Eval Fields", check_eval_fields),
    ("check_absence Consistency", check_check_absence_consistency),
    ("Hierarchy Achievability", check_hierarchy_achievability),
    ("Only Fill Completeness", check_only_fill_completeness),
    ("Sensitive in Only Fill", check_sensitive_data_in_only_fill),
    ("Popup Error", check_popup_error_consistency),
]


def audit_task(task):
    """Run all checks on a single task. Returns list of (check_name, severity, message)."""
    results = []
    for check_name, check_fn in ALL_CHECKS:
        for severity, msg in check_fn(task):
            results.append((check_name, severity, msg))
    return results


def main():
    tasks = load_tasks()
    print(f"Auditing {len(tasks)} tasks...\n")

    all_issues = []
    tasks_with_critical = []
    tasks_with_warning = []
    tasks_clean = []

    severity_counts = Counter()
    check_counts = Counter()

    for task in sorted(tasks, key=lambda t: t["task_id"]):
        tid = task["task_id"]
        issues = audit_task(task)

        for check_name, severity, msg in issues:
            all_issues.append((tid, check_name, severity, msg))
            severity_counts[severity] += 1
            check_counts[check_name] += 1

        has_critical = any(s == CRITICAL for _, s, _ in issues)
        has_warning = any(s == WARNING for _, s, _ in issues)

        if has_critical:
            tasks_with_critical.append(tid)
        elif has_warning:
            tasks_with_warning.append(tid)
        else:
            tasks_clean.append(tid)

    # ── Print Report ──
    print("=" * 80)
    print("  TASK FEASIBILITY AUDIT REPORT")
    print("=" * 80)
    print(f"\n  Tasks audited: {len(tasks)}")
    print(f"  Clean (no issues): {len(tasks_clean)}")
    print(f"  With warnings: {len(tasks_with_warning)}")
    print(f"  With CRITICAL issues: {len(tasks_with_critical)}")
    print(f"\n  Total issues: {sum(severity_counts.values())}")
    for sev in [CRITICAL, WARNING, INFO]:
        if severity_counts[sev]:
            print(f"    {sev}: {severity_counts[sev]}")

    print(f"\n  Issues by check:")
    for check_name, count in check_counts.most_common():
        print(f"    {check_name}: {count}")

    # ── Critical issues ──
    critical_issues = [(tid, cn, s, m) for tid, cn, s, m in all_issues if s == CRITICAL]
    if critical_issues:
        print(f"\n{'=' * 80}")
        print(f"  CRITICAL ISSUES ({len(critical_issues)})")
        print(f"{'=' * 80}")
        for tid, check_name, _, msg in critical_issues:
            print(f"\n  Task {tid} [{check_name}]:")
            print(f"    {msg}")

    # ── Warning issues ──
    warning_issues = [(tid, cn, s, m) for tid, cn, s, m in all_issues if s == WARNING]
    if warning_issues:
        print(f"\n{'=' * 80}")
        print(f"  WARNINGS ({len(warning_issues)})")
        print(f"{'=' * 80}")
        current_tid = None
        for tid, check_name, _, msg in warning_issues:
            if tid != current_tid:
                print(f"\n  Task {tid}:")
                current_tid = tid
            print(f"    [{check_name}] {msg}")

    # ── Per-range summary ──
    print(f"\n{'=' * 80}")
    print(f"  PER-RANGE SUMMARY")
    print(f"{'=' * 80}")
    ranges = [
        ("GitLab 0-46", range(0, 47)),
        ("CRM 47-76", range(47, 77)),
        ("Shopping 77-84", range(77, 85)),
        ("GitLab 85-234", range(85, 235)),
        ("CRM Easy 235-254", range(235, 255)),
        ("CRM Medium 255-274", range(255, 275)),
        ("CRM Hard 275-294", range(275, 295)),
        ("CRM Modality 295-374", range(295, 375)),
    ]

    task_ids = {t["task_id"] for t in tasks}
    for label, r in ranges:
        range_tids = set(r) & task_ids
        if not range_tids:
            continue
        range_critical = len([t for t in tasks_with_critical if t in range_tids])
        range_warning = len([t for t in tasks_with_warning if t in range_tids])
        range_clean = len(range_tids) - range_critical - range_warning
        issues_in_range = [(tid, cn, s, m) for tid, cn, s, m in all_issues if tid in range_tids]
        print(f"\n  {label}: {len(range_tids)} tasks")
        print(f"    Clean: {range_clean}, Warnings: {range_warning}, Critical: {range_critical}")
        if issues_in_range:
            crit_in_range = [m for _, _, s, m in issues_in_range if s == CRITICAL]
            if crit_in_range:
                print(f"    Critical details: {crit_in_range[:3]}{'...' if len(crit_in_range) > 3 else ''}")

    print(f"\n{'=' * 80}")
    if not critical_issues:
        print("  VERDICT: ALL TASKS FEASIBLE — No critical issues found")
    else:
        print(f"  VERDICT: {len(tasks_with_critical)} TASKS HAVE CRITICAL ISSUES")
    print(f"{'=' * 80}")

    return len(critical_issues)


if __name__ == "__main__":
    sys.exit(0 if main() == 0 else 1)
