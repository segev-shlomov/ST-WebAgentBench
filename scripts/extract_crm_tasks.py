#!/usr/bin/env python3
"""
Extract all CRM (SuiteCRM) tasks from test.raw.json and generate
analysis template files in .task_analysis/tasks/{group}/.

Run from the project root:
    python scripts/extract_crm_tasks.py
"""

import json
import os
from pathlib import Path
from collections import defaultdict

PROJECT_ROOT = Path(__file__).parent.parent
TASK_JSON = PROJECT_ROOT / "stwebagentbench" / "test.raw.json"
OUTPUT_ROOT = PROJECT_ROOT / ".task_analysis" / "tasks"


def get_group(task_id: int) -> str:
    if 47 <= task_id <= 76:
        return "group_core"
    elif 235 <= task_id <= 254:
        return "group_advanced_easy"
    elif 255 <= task_id <= 274:
        return "group_advanced_medium"
    elif 275 <= task_id <= 294:
        return "group_advanced_hard"
    elif 295 <= task_id <= 374:
        return "group_modality"
    else:
        return "group_other"


def get_tier(task_id: int, task: dict) -> str:
    meta = task.get("task_metadata", {})
    if meta.get("difficulty"):
        return meta["difficulty"]
    if 47 <= task_id <= 76:
        return "core"
    elif 235 <= task_id <= 254:
        return "easy"
    elif 255 <= task_id <= 274:
        return "medium"
    elif 275 <= task_id <= 294:
        return "hard"
    elif 295 <= task_id <= 374:
        return f"modality-{meta.get('modality_class', 'unknown')}"
    return "unknown"


def summarize_eval(task: dict) -> str:
    ev = task.get("eval", {})
    eval_types = ev.get("eval_types", [])
    lines = []

    if "program_html" in eval_types:
        for ph in ev.get("program_html", []):
            rc = ph.get("required_contents", {})
            must_include = rc.get("must_include", [])
            must_not = rc.get("must_not_include", [])
            exact = rc.get("exact_match")
            if must_include:
                lines.append(f"  - HTML must include: `{must_include[0][:80]}`")
            if must_not:
                lines.append(f"  - HTML must NOT include: `{must_not[0][:80]}`")
            if exact:
                lines.append(f"  - HTML exact match: `{exact[:80]}`")
    elif "string_match" in eval_types:
        ra = ev.get("reference_answers", {})
        if ra:
            lines.append(f"  - String match: `{list(ra.values())[0][:80]}`")

    return "\n".join(lines) if lines else "  - (no eval details parsed)"


def summarize_policies(task: dict) -> tuple[int, str, list[str]]:
    """Returns (count, categories_string, list of brief policy summaries)."""
    policies = task.get("policies", [])
    cats = defaultdict(int)
    summaries = []

    for p in policies:
        cat = p.get("policy_category", "unknown")
        cats[cat] += 1
        tmpl = p.get("policy_template_id", "?")
        src = p.get("source", "?")
        desc = p.get("description", "")[:80]
        ev_types = p.get("eval", {}).get("eval_types", [])
        summaries.append(f"  - [{src}] `{tmpl}` ({', '.join(ev_types)}): {desc}")

    cat_str = ", ".join(f"{cat}({n})" for cat, n in cats.items())
    return len(policies), cat_str, summaries


def make_template(task: dict) -> str:
    tid = task["task_id"]
    intent = task.get("intent", "")
    intent_short = intent[:60] + "..." if len(intent) > 60 else intent
    tmpl_id = task.get("intent_template_id", "?")
    tier = get_tier(tid, task)
    group = get_group(tid)
    group_label = group.replace("group_", "").replace("_", " ")
    has_setup = "Yes" if task.get("setup_scripts") else "No"
    eval_summary = summarize_eval(task)
    n_policies, cat_str, policy_summaries = summarize_policies(task)

    meta = task.get("task_metadata", {})
    modality_info = ""
    if meta:
        modality_info = f"\n**Modality Class:** {meta.get('modality_class', '?')} | **Category:** {meta.get('category', '?')}"

    policy_detail = "\n".join(policy_summaries)

    return f"""# Task {tid}: {intent_short}

**Intent Template ID:** {tmpl_id} | **Tier:** {tier} | **Group:** {group_label}{modality_info}
**Trajectory:** `data/STWebAgentBenchEnv/browsergym/STWebAgentBenchEnv.{tid}/exp_1/`

---

## Definition

- **Intent:** {intent}
- **Eval Types:** {task.get('eval', {}).get('eval_types', [])}
- **Eval Criteria:**
{eval_summary}
- **Policies:** {n_policies} policies — {cat_str}
- **Setup Scripts:** {has_setup}
- **Require Reset:** {task.get('require_reset', False)}

### Policies Detail
{policy_detail}

---

## Static Analysis *(pre-run assessment)*

### Intent Quality
**Score:** /5 | **Issue type:** none / ambiguity / missing-context / vague / incorrect
**Notes:**
>

### Evaluation Correctness
**Risk:** low / medium / high
**False Positive Risk:**
>
**False Negative Risk:**
>
**Notes:**
>

### Policy Integration
**Relevance:** good / partial / poor
**Calibration Issues:**
>
**Contradictions / Gaps:**
>
**Notes:**
>

### Feasibility
**Assessment:** feasible / risky / infeasible
**Data Dependencies:**
>
**State Risks (concurrent tasks, missing records, etc.):**
>
**Notes:**
>

---

## Dynamic Analysis *(post agent run)*

### Agent Outcome
**Result:** success / failure / policy-violation | **Steps:** ?
**Violated Policies:**

### Observations
**Did agent succeed when it should have?**
>
**Policy violations — real or false positive?**
>
**Eval correctness — did score match actual completion?**
>

---

## Summary

**Quality Score:** /5
**Key Issues:**
-
**Priority Fix:**
>
**Suggestions:**
-
"""


def main():
    print(f"Reading tasks from {TASK_JSON}")
    with open(TASK_JSON) as f:
        all_tasks = json.load(f)

    crm_tasks = [t for t in all_tasks if t.get("sites") == ["suitecrm"]]
    crm_tasks.sort(key=lambda t: t["task_id"])
    print(f"Found {len(crm_tasks)} CRM tasks")

    # Count by group
    group_counts = defaultdict(int)
    for t in crm_tasks:
        group_counts[get_group(t["task_id"])] += 1
    for g, n in sorted(group_counts.items()):
        print(f"  {g}: {n} tasks")

    # Create output directories
    groups = set(get_group(t["task_id"]) for t in crm_tasks)
    for g in groups:
        (OUTPUT_ROOT / g).mkdir(parents=True, exist_ok=True)

    # Generate template files
    created = 0
    skipped = 0
    for task in crm_tasks:
        tid = task["task_id"]
        group = get_group(tid)
        out_path = OUTPUT_ROOT / group / f"task_{tid:03d}.md"

        if out_path.exists():
            skipped += 1
            continue

        content = make_template(task)
        out_path.write_text(content)
        created += 1

    print(f"\nDone: {created} created, {skipped} already existed")
    print(f"Output: {OUTPUT_ROOT}")

    # Print a task ID index
    index_lines = ["# CRM Task Index\n"]
    last_group = None
    for t in crm_tasks:
        g = get_group(t["task_id"])
        if g != last_group:
            index_lines.append(f"\n## {g.replace('group_', '').replace('_', ' ').title()}\n")
            last_group = g
        intent_short = t["intent"][:70] + "..." if len(t["intent"]) > 70 else t["intent"]
        index_lines.append(f"- [{t['task_id']}] {intent_short}")

    index_path = OUTPUT_ROOT / "INDEX.md"
    index_path.write_text("\n".join(index_lines))
    print(f"Index written to {index_path}")


if __name__ == "__main__":
    main()
