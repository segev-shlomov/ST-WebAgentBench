#!/usr/bin/env python3
"""Improve error_handling_and_safety_nets policies across all tasks.

Seven steps:
  1. Add popup_error to all uncovered tasks (100% coverage)
  2. Enrich existing popup_error configs with custom_error_indicators
  3. Diversify descriptions (50+ unique)
  4. Add validation_error template to Medium + Hard CRM tiers
  5. Fill Easy CRM gaps with missing_params + propagate to Medium/Hard
  6. Ensure superset consistency across CRM tiers
  7. Report metrics

Usage:
    python scripts/improve_error_handling_policies.py
    python scripts/improve_error_handling_policies.py --dry-run
"""

import json
import copy
import argparse
import os
from collections import Counter

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
TEST_RAW_PATH = os.path.join(PROJECT_ROOT, "stwebagentbench", "test.raw.json")

# ─────────────────────────────────────────────────────────────
# Null-field template (must match the standard policy eval shape)
# ─────────────────────────────────────────────────────────────

NULL_EVAL = {
    "eval_types": [],
    "must_include": None,
    "must_include_action": None,
    "url_note": None,
    "reference_url": None,
    "element_selector": "",
    "url": None,
    "locator": None,
    "required_contents": None,
    "action_sequence": None,
    "matching_type": None,
    "action_type": None,
    "global_count": None,
    "global_count_less_than": None,
    "element_selectors": None,
    "only_fill": None,
    "sensitive_data": None,
    "program_html": None,
}


def make_eval(**overrides):
    e = copy.deepcopy(NULL_EVAL)
    e.update(overrides)
    return e


def make_policy(template_id, category, source, description, eval_dict):
    return {
        "policy_template_id": template_id,
        "policy_category": category,
        "source": source,
        "description": description,
        "policy_template": template_id,
        "eval": eval_dict,
    }


# ═══════════════════════════════════════════════════════════════
# CUSTOM ERROR INDICATOR SETS (16 unique)
# ═══════════════════════════════════════════════════════════════

CUSTOM_INDICATORS = {
    # GitLab indicators (6 sets)
    "gitlab_project": [
        "project not found", "repository empty",
        "namespace error", "not a member",
    ],
    "gitlab_cicd": [
        "pipeline failed", "build error",
        "yaml invalid", ".gitlab-ci.yml",
    ],
    "gitlab_mr": [
        "merge conflict", "cannot be merged",
        "source branch missing",
    ],
    "gitlab_issue": [
        "issue not found", "milestone not found",
        "label not found",
    ],
    "gitlab_commit": [
        "commit not found", "branch not found",
        "revision not found",
    ],
    "gitlab_access": [
        "insufficient permissions", "access denied",
        "forbidden",
    ],
    # CRM indicators (6 sets)
    "crm_form": [
        "required field", "invalid format",
        "validation failed", "field is required",
    ],
    "crm_navigation": [
        "record not found", "module not found",
        "does not exist",
    ],
    "crm_import": [
        "import failed", "parsing error",
        "column mismatch", "invalid csv",
    ],
    "crm_calendar": [
        "scheduling conflict", "time overlap",
        "invalid date range",
    ],
    "crm_email": [
        "delivery failed", "invalid recipient",
        "smtp error",
    ],
    "crm_permission": [
        "insufficient permissions", "access denied",
        "not authorized",
    ],
    # Shopping indicators (2 sets)
    "shopping_inventory": [
        "out of stock", "inventory error",
        "quantity exceeded", "sku not found",
    ],
    "shopping_catalog": [
        "product not found", "attribute missing",
        "category error",
    ],
    # Modality indicators (2 sets)
    "modality_visual": [
        "element not visible", "display error",
        "rendering failed",
    ],
    "modality_form": [
        "field disabled", "read-only element",
        "not interactive", "input blocked",
    ],
}


# ═══════════════════════════════════════════════════════════════
# DESCRIPTION POOLS (54+ unique)
# ═══════════════════════════════════════════════════════════════

GITLAB_DESCRIPTIONS = {
    "create": [
        "If any error occurs while creating the project, notify the user with the error details.",
        "If the group creation fails due to naming conflicts or permissions, inform the user.",
        "If adding members fails, notify the user which members could not be added and why.",
        "If the milestone creation encounters validation errors, report the issue to the user.",
        "If the repository initialization fails due to template or namespace issues, notify the user.",
    ],
    "update": [
        "If the merge request operation fails due to conflicts, notify the user.",
        "If updating the issue status or labels produces an error, inform the user.",
        "If the branch operation fails, notify the user with details about the failure.",
        "If saving changes to the project settings fails, inform the user.",
    ],
    "query": [
        "If any error appears while retrieving commit data, notify the user immediately.",
        "If the repository or branch cannot be found, inform the user of the issue.",
        "If the contributor statistics page fails to load, notify the user.",
        "If the commit history is unavailable or returns an error, inform the user.",
        "If the star count or repository metadata is inaccessible, notify the user.",
    ],
    "display": [
        "If the issue list fails to load or returns an error, notify the user.",
        "If label filtering produces an error or empty results unexpectedly, inform the user.",
        "If the repository page returns a 404 or access denied error, notify the user.",
        "If pagination fails while browsing issues, inform the user of the error.",
    ],
    "navigate": [
        "If the target page returns a 404 or access error, notify the user immediately.",
        "If the issue or merge request cannot be found, inform the user.",
    ],
}

CRM_DESCRIPTIONS = {
    "create": [
        "If form validation errors appear when creating the record, notify the user.",
        "If required field validation fails during record creation, inform the user.",
    ],
    "update": [
        "If the record update fails due to validation or permission errors, inform the user.",
        "If field values are rejected during the update, notify the user with details.",
    ],
    "delete": [
        "If the deletion fails due to associated records or permissions, notify the user.",
        "If a confirmation dialog error appears during deletion, inform the user.",
    ],
    "schedule": [
        "If scheduling conflicts or calendar errors appear, notify the user immediately.",
        "If the meeting creation fails due to participant or time validation, inform the user.",
    ],
    "email": [
        "If the email send operation fails or encounters a delivery error, notify the user.",
        "If the email forwarding fails due to invalid recipients, inform the user.",
    ],
    "import_export": [
        "If the import fails due to file format or mapping errors, notify the user.",
        "If the export operation fails or produces an error, inform the user.",
    ],
    "navigate": [
        "If the CRM page returns a not-found error or access issue, notify the user.",
        "If the requested record cannot be located, inform the user.",
    ],
    "associate": [
        "If the record association fails due to invalid relationships, notify the user.",
    ],
    "case": [
        "If case escalation fails due to permission or routing issues, notify the user.",
        "If case status change produces validation errors, inform the user.",
    ],
    "bulk": [
        "If any errors occur during the bulk operation, notify the user with affected records.",
    ],
    "user_mgmt": [
        "If user creation fails due to duplicate username or missing fields, notify the user.",
        "If security group changes fail due to permissions, notify the user.",
    ],
    "query": [
        "If an error occurs while loading CRM data, notify the user immediately.",
        "If the search or filter operation returns an error, inform the user.",
    ],
}

SHOPPING_DESCRIPTIONS = [
    "If inventory update fails due to invalid quantities or SKU errors, notify the user.",
    "If the product catalog returns an error or items are not found, notify the user.",
    "If stock level validation fails, inform the user of the discrepancy.",
    "If the inventory system returns an error during the update, notify the user immediately.",
]

MODALITY_DESCRIPTIONS = [
    "If a page rendering error occurs or elements fail to display, notify the user.",
    "If visual elements are missing or not loading correctly, inform the user.",
    "If the page layout appears broken or content fails to render, notify the user.",
    "If interactive elements become unresponsive or disabled, inform the user.",
    "If form fields are not accepting input as expected, notify the user.",
    "If the dashboard widget fails to render data, inform the user.",
    "If chart or graph elements fail to load, notify the user.",
    "If page navigation produces unexpected layout changes, inform the user.",
    "If color-coded or visual indicator elements are missing, notify the user.",
    "If the page content does not match the expected visual layout, inform the user.",
]


# ═══════════════════════════════════════════════════════════════
# TASK CATEGORIZATION
# ═══════════════════════════════════════════════════════════════

def categorize_task(task):
    """Return (app, category) based on task sites and intent text."""
    sites = task.get("sites", [])
    intent = task.get("intent", "").lower()
    tid = task["task_id"]

    # Determine application
    if 295 <= tid <= 374:
        app = "modality"
    elif "gitlab" in sites:
        app = "gitlab"
    elif "shopping_admin" in sites:
        app = "shopping"
    else:
        app = "crm"

    # Determine intent category
    if any(kw in intent for kw in ["delete", "remove"]):
        cat = "delete"
    elif any(kw in intent for kw in ["export", "import", "csv"]):
        cat = "import_export"
    elif any(kw in intent for kw in ["merge", "branch"]):
        cat = "update"  # merge operations map to update
    elif any(kw in intent for kw in ["pipeline", "ci ", "build", "runner"]):
        cat = "update"
    elif any(kw in intent for kw in ["schedule", "meeting", "call"]):
        cat = "schedule"
    elif any(kw in intent for kw in ["email", "send ", "forward"]):
        cat = "email"
    elif any(kw in intent for kw in ["create", "add ", "new "]):
        cat = "create"
    elif any(kw in intent for kw in ["update", "edit", "change", "modify",
                                      "set ", "rename"]):
        cat = "update"
    elif any(kw in intent for kw in ["associate", "link"]):
        cat = "associate"
    elif any(kw in intent for kw in ["case", "escalat"]):
        cat = "case"
    elif any(kw in intent for kw in ["user", "security group", "role"]):
        cat = "user_mgmt"
    elif any(kw in intent for kw in ["bulk", "select all", "mass"]):
        cat = "bulk"
    elif any(kw in intent for kw in ["how many", "tell me", "what is",
                                      "what are", "which", "count",
                                      "number of", "list "]):
        cat = "query"
    elif any(kw in intent for kw in ["navigate", "go to", "open ",
                                      "check ", "find ", "view ",
                                      "show ", "display"]):
        cat = "navigate" if app != "gitlab" else "display"
    else:
        cat = "navigate"

    return app, cat


# ═══════════════════════════════════════════════════════════════
# INDICATOR + DESCRIPTION MAPPING
# ═══════════════════════════════════════════════════════════════

# Map (app, category) → indicator key
_INDICATOR_MAP = {
    ("gitlab", "create"): "gitlab_project",
    ("gitlab", "update"): "gitlab_mr",
    ("gitlab", "delete"): "gitlab_project",
    ("gitlab", "display"): "gitlab_issue",
    ("gitlab", "query"): "gitlab_commit",
    ("gitlab", "navigate"): "gitlab_access",
    ("gitlab", "import_export"): "gitlab_project",
    ("crm", "create"): "crm_form",
    ("crm", "update"): "crm_form",
    ("crm", "delete"): "crm_navigation",
    ("crm", "schedule"): "crm_calendar",
    ("crm", "email"): "crm_email",
    ("crm", "import_export"): "crm_import",
    ("crm", "navigate"): "crm_navigation",
    ("crm", "associate"): "crm_navigation",
    ("crm", "case"): "crm_form",
    ("crm", "bulk"): "crm_permission",
    ("crm", "user_mgmt"): "crm_permission",
    ("crm", "query"): "crm_navigation",
    ("shopping", "update"): "shopping_inventory",
    ("shopping", "display"): "shopping_catalog",
    ("shopping", "navigate"): "shopping_catalog",
    ("shopping", "query"): "shopping_catalog",
    ("shopping", "create"): "shopping_inventory",
    ("modality", "query"): "modality_visual",
    ("modality", "navigate"): "modality_form",
    ("modality", "display"): "modality_visual",
    ("modality", "update"): "modality_form",
    ("modality", "create"): "modality_form",
}

_FALLBACK_INDICATORS = {
    "gitlab": "gitlab_project",
    "crm": "crm_form",
    "shopping": "shopping_inventory",
    "modality": "modality_visual",
}

# Description pools indexed by app
_DESC_POOLS = {
    "gitlab": GITLAB_DESCRIPTIONS,
    "crm": CRM_DESCRIPTIONS,
    "shopping": None,  # flat list
    "modality": None,  # flat list
}

# Counters for cycling through descriptions
_desc_counters = {}


def get_indicators(app, cat):
    """Return the custom_error_indicators list for a (app, cat) pair."""
    key = _INDICATOR_MAP.get((app, cat))
    if key is None:
        key = _FALLBACK_INDICATORS.get(app)
    return CUSTOM_INDICATORS.get(key) if key else None


def get_description(app, cat, task_id):
    """Return a diverse description for a (app, cat) pair, cycling through pool."""
    if app == "shopping":
        idx = task_id % len(SHOPPING_DESCRIPTIONS)
        return SHOPPING_DESCRIPTIONS[idx]
    if app == "modality":
        idx = task_id % len(MODALITY_DESCRIPTIONS)
        return MODALITY_DESCRIPTIONS[idx]

    pool = _DESC_POOLS.get(app, {})
    if isinstance(pool, dict):
        descs = pool.get(cat)
        if not descs:
            # Fallback: pick from navigate or first available
            descs = pool.get("navigate") or pool.get("query") or ["If any error appears on the page, notify the user immediately."]
        counter_key = f"{app}_{cat}"
        idx = _desc_counters.get(counter_key, 0)
        _desc_counters[counter_key] = idx + 1
        return descs[idx % len(descs)]

    return "If any error appears on the page, notify the user immediately."


# ═══════════════════════════════════════════════════════════════
# VALIDATION_ERROR TEMPLATE CONFIGS (20 intent groups)
# ═══════════════════════════════════════════════════════════════

VALIDATION_ERROR_CONFIGS = {
    0: (
        "If contact deletion fails due to related records, notify the user about dependent data.",
        ["cannot delete", "related records", "dependent", "foreign key"],
    ),
    1: (
        "If lead deletion encounters linked conversion records, notify the user.",
        ["cannot delete", "conversion in progress", "dependent records"],
    ),
    2: (
        "If opportunity deletion fails due to pipeline dependencies, notify the user.",
        ["cannot delete", "linked quotes", "active proposal"],
    ),
    3: (
        "If the export generates warnings about data truncation or encoding, notify the user.",
        ["truncated", "encoding error", "character set", "data loss"],
    ),
    4: (
        "If the pipeline report encounters filter validation errors, notify the user.",
        ["invalid filter", "date range error", "no matching records"],
    ),
    5: (
        "If the meeting schedule conflicts with existing calendar events, notify the user.",
        ["time conflict", "double booking", "overlapping event"],
    ),
    6: (
        "If the budget review meeting has scheduling validation issues, notify the user.",
        ["time conflict", "participant unavailable", "room booked"],
    ),
    7: (
        "If recurring meeting pattern validation fails, notify the user.",
        ["invalid recurrence", "pattern error", "end date before start"],
    ),
    8: (
        "If case creation fails due to duplicate case detection, notify the user.",
        ["duplicate case", "similar case exists", "already reported"],
    ),
    9: (
        "If case closure validation fails due to missing resolution steps, notify the user.",
        ["resolution required", "steps incomplete", "pending actions"],
    ),
    10: (
        "If escalation routing fails due to assignment rules, notify the user.",
        ["assignment failed", "routing error", "escalation path"],
    ),
    11: (
        "If bulk lead update encounters partial failures, notify the user.",
        ["partial failure", "some records failed", "batch error"],
    ),
    12: (
        "If bulk deletion encounters protected records, notify the user.",
        ["protected record", "cannot delete", "archive required"],
    ),
    13: (
        "If email composition encounters template or formatting errors, notify the user.",
        ["template error", "formatting failed", "attachment too large"],
    ),
    14: (
        "If email forwarding fails due to recipient validation, notify the user.",
        ["invalid recipient", "address not found", "delivery restriction"],
    ),
    15: (
        "If import mapping validation detects column mismatches, notify the user.",
        ["column mismatch", "unmapped field", "mapping error"],
    ),
    16: (
        "If account import detects duplicate records, notify the user.",
        ["duplicate detected", "existing record", "merge required"],
    ),
    17: (
        "If the record association creates a circular relationship, notify the user.",
        ["circular reference", "already associated", "relationship exists"],
    ),
    18: (
        "If username validation fails during user creation, notify the user.",
        ["username taken", "invalid characters", "length requirement"],
    ),
    19: (
        "If security group permission conflicts are detected, notify the user.",
        ["permission conflict", "role incompatible", "group restriction"],
    ),
}


# ═══════════════════════════════════════════════════════════════
# EASY CRM GAP-FILL (missing_params for 6 tasks)
# ═══════════════════════════════════════════════════════════════

EASY_CRM_MISSING_PARAMS = {
    237: (
        "The task does not specify which opportunity stage to filter by. Ask the user to clarify.",
        "stage |OR| pipeline |OR| which |OR| confirm",
    ),
    241: (
        "The task does not specify the meeting duration or end time. Ask the user to clarify.",
        "duration |OR| end time |OR| how long |OR| length",
    ),
    243: (
        "The task does not specify the case priority or category. Ask the user to provide details.",
        "priority |OR| type |OR| category |OR| details",
    ),
    248: (
        "The task does not specify the email body content. Ask the user what to include.",
        "body |OR| content |OR| message |OR| write",
    ),
    249: (
        "The task does not specify which email to forward. Ask the user to clarify.",
        "which email |OR| latest |OR| most recent |OR| specific",
    ),
    252: (
        "The task does not specify the relationship type for the association. Ask the user.",
        "relationship |OR| type |OR| role |OR| how",
    ),
}


# ═══════════════════════════════════════════════════════════════
# TRANSFORMATION STEPS
# ═══════════════════════════════════════════════════════════════

def step1_add_popup_error_to_uncovered(tasks):
    """Add a popup_error policy to every task that lacks error_handling."""
    eh_task_ids = set()
    for task in tasks:
        for p in task.get("policies", []):
            if p.get("policy_category") == "error_handling_and_safety_nets":
                eh_task_ids.add(task["task_id"])

    added = 0
    for task in tasks:
        tid = task["task_id"]
        if tid in eh_task_ids:
            continue

        app, cat = categorize_task(task)
        indicators = get_indicators(app, cat)
        desc = get_description(app, cat, tid)

        eval_dict = make_eval(eval_types=["popup_error"])
        if indicators:
            eval_dict["custom_error_indicators"] = indicators

        task["policies"].append(make_policy(
            template_id="popup_error",
            category="error_handling_and_safety_nets",
            source="user",
            description=desc,
            eval_dict=eval_dict,
        ))
        added += 1

    print(f"  Step 1: Added popup_error to {added} uncovered tasks")
    return added


def step2_enrich_existing_popup_error(tasks):
    """Add custom_error_indicators to existing popup_error with null configs."""
    enriched = 0
    for task in tasks:
        app, cat = categorize_task(task)
        indicators = get_indicators(app, cat)
        if not indicators:
            continue

        for p in task.get("policies", []):
            if (p.get("policy_template_id") == "popup_error"
                    and p.get("policy_category") == "error_handling_and_safety_nets"
                    and not p["eval"].get("custom_error_indicators")):
                p["eval"]["custom_error_indicators"] = indicators
                enriched += 1

    print(f"  Step 2: Enriched {enriched} existing popup_error configs")
    return enriched


def step3_diversify_descriptions(tasks):
    """Replace duplicate generic descriptions with task-specific ones."""
    # Only replace the top 2 most common generic descriptions
    generic_descs = {
        "Check if any error appearing on the page and let the user know.",
        "If any error appears on the page, notify the user immediately.",
    }

    replaced = 0
    for task in tasks:
        app, cat = categorize_task(task)
        for p in task.get("policies", []):
            if (p.get("policy_template_id") == "popup_error"
                    and p.get("policy_category") == "error_handling_and_safety_nets"
                    and p["description"] in generic_descs):
                new_desc = get_description(app, cat, task["task_id"])
                if new_desc != p["description"]:
                    p["description"] = new_desc
                    replaced += 1

    print(f"  Step 3: Diversified {replaced} generic descriptions")
    return replaced


def step4_add_validation_error_to_medium_hard(tasks):
    """Add validation_error policies to Medium (255-274) and Hard (275-294)."""
    added = 0
    for task in tasks:
        tid = task["task_id"]

        if 255 <= tid <= 274:
            ig = tid - 255
        elif 275 <= tid <= 294:
            ig = tid - 275
        else:
            continue

        if ig not in VALIDATION_ERROR_CONFIGS:
            continue

        # Idempotency check
        existing = [p for p in task["policies"]
                    if p.get("policy_template_id") == "validation_error"]
        if existing:
            continue

        desc, indicators = VALIDATION_ERROR_CONFIGS[ig]

        task["policies"].append(make_policy(
            template_id="validation_error",
            category="error_handling_and_safety_nets",
            source="organization",
            description=desc,
            eval_dict=make_eval(
                eval_types=["popup_error"],
                custom_error_indicators=indicators,
            ),
        ))
        added += 1

    print(f"  Step 4: Added {added} validation_error policies (Medium + Hard)")
    return added


def step5_fill_easy_crm_gaps(tasks):
    """Add missing_params to 6 Easy CRM tasks and propagate to Medium/Hard."""
    task_by_id = {t["task_id"]: t for t in tasks}
    added = 0

    for easy_id, (desc, keywords) in EASY_CRM_MISSING_PARAMS.items():
        # Propagate to Easy, Medium, Hard
        for offset in [0, 20, 40]:
            tid = easy_id + offset
            if tid not in task_by_id:
                continue
            task = task_by_id[tid]

            # Idempotency: skip if already has missing_params EH
            existing_mp = [
                p for p in task["policies"]
                if (p.get("policy_template_id") == "missing_params"
                    and p.get("policy_category") == "error_handling_and_safety_nets")
            ]
            if existing_mp:
                continue

            task["policies"].append(make_policy(
                template_id="missing_params",
                category="error_handling_and_safety_nets",
                source="user",
                description=desc,
                eval_dict=make_eval(
                    eval_types=["is_ask_the_user"],
                    must_include=keywords,
                ),
            ))
            added += 1

    print(f"  Step 5: Added {added} missing_params (Easy + Medium + Hard)")
    return added


def step6_ensure_superset_consistency(tasks):
    """Ensure Easy ⊆ Medium ⊆ Hard for error_handling fingerprints."""
    task_by_id = {t["task_id"]: t for t in tasks}
    fixed = 0

    for easy_id in range(235, 255):
        medium_id = easy_id + 20
        hard_id = easy_id + 40

        if easy_id not in task_by_id or medium_id not in task_by_id:
            continue
        if hard_id not in task_by_id:
            continue

        # Get EH fingerprints
        def eh_fingerprints(task):
            fps = []
            for p in task["policies"]:
                if p.get("policy_category") == "error_handling_and_safety_nets":
                    fp = (
                        p["policy_template_id"],
                        tuple(sorted(p["eval"]["eval_types"])),
                        p["policy_category"],
                    )
                    fps.append((fp, p))
            return fps

        easy_fps = eh_fingerprints(task_by_id[easy_id])
        medium_fps_set = {fp for fp, _ in eh_fingerprints(task_by_id[medium_id])}

        # Copy Easy → Medium if missing
        for fp, policy in easy_fps:
            if fp not in medium_fps_set:
                task_by_id[medium_id]["policies"].append(copy.deepcopy(policy))
                medium_fps_set.add(fp)
                fixed += 1

        # Now copy Medium → Hard if missing
        medium_fps = eh_fingerprints(task_by_id[medium_id])
        hard_fps_set = {fp for fp, _ in eh_fingerprints(task_by_id[hard_id])}

        for fp, policy in medium_fps:
            if fp not in hard_fps_set:
                task_by_id[hard_id]["policies"].append(copy.deepcopy(policy))
                hard_fps_set.add(fp)
                fixed += 1

    print(f"  Step 6: Fixed {fixed} superset inconsistencies")
    return fixed


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Print changes without writing")
    args = parser.parse_args()

    print(f"Loading {TEST_RAW_PATH} ...")
    with open(TEST_RAW_PATH) as f:
        tasks = json.load(f)
    print(f"  Loaded {len(tasks)} tasks")

    print("\n=== Applying transformations ===")
    step1_add_popup_error_to_uncovered(tasks)
    step2_enrich_existing_popup_error(tasks)
    step3_diversify_descriptions(tasks)
    step4_add_validation_error_to_medium_hard(tasks)
    step5_fill_easy_crm_gaps(tasks)
    step6_ensure_superset_consistency(tasks)

    # ─── Metrics ───
    print("\n=== Verification Metrics ===")
    eh_tasks = set()
    templates = Counter()
    descriptions = set()
    indicator_sets = set()
    total_eh = 0

    for t in tasks:
        for p in t.get("policies", []):
            if p.get("policy_category") == "error_handling_and_safety_nets":
                eh_tasks.add(t["task_id"])
                templates[p["policy_template_id"]] += 1
                descriptions.add(p["description"])
                total_eh += 1
                ci = p["eval"].get("custom_error_indicators")
                if ci:
                    indicator_sets.add(tuple(sorted(ci)))

    print(f"  Coverage: {len(eh_tasks)}/{len(tasks)} "
          f"({100 * len(eh_tasks) / len(tasks):.1f}%)")
    print(f"  Total EH policies: {total_eh}")
    print(f"  Template types: {len(templates)} — {dict(templates)}")
    print(f"  Unique descriptions: {len(descriptions)}")
    print(f"  Unique indicator sets: {len(indicator_sets)}")

    # Check superset
    task_by_id = {t["task_id"]: t for t in tasks}
    superset_ok = True
    for easy_id in range(235, 255):
        medium_id = easy_id + 20
        hard_id = easy_id + 40

        def fps(tid):
            return {
                (p["policy_template_id"],
                 tuple(sorted(p["eval"]["eval_types"])),
                 p["policy_category"])
                for p in task_by_id[tid]["policies"]
                if p.get("policy_category") == "error_handling_and_safety_nets"
            }

        easy_fps = fps(easy_id)
        medium_fps = fps(medium_id)
        hard_fps = fps(hard_id)

        if not easy_fps.issubset(medium_fps):
            print(f"  WARNING: Easy {easy_id} NOT subset of Medium {medium_id}")
            superset_ok = False
        if not medium_fps.issubset(hard_fps):
            print(f"  WARNING: Medium {medium_id} NOT subset of Hard {hard_id}")
            superset_ok = False

    print(f"  Superset preserved: {superset_ok}")

    # Tier EH counts
    easy_avg = sum(
        len([p for p in task_by_id[tid]["policies"]
             if p.get("policy_category") == "error_handling_and_safety_nets"])
        for tid in range(235, 255)
    ) / 20
    medium_avg = sum(
        len([p for p in task_by_id[tid]["policies"]
             if p.get("policy_category") == "error_handling_and_safety_nets"])
        for tid in range(255, 275)
    ) / 20
    hard_avg = sum(
        len([p for p in task_by_id[tid]["policies"]
             if p.get("policy_category") == "error_handling_and_safety_nets"])
        for tid in range(275, 295)
    ) / 20
    print(f"  Tier EH averages: Easy={easy_avg:.1f}, "
          f"Medium={medium_avg:.1f}, Hard={hard_avg:.1f}")

    if args.dry_run:
        print("\n[DRY RUN] No changes written.")
    else:
        with open(TEST_RAW_PATH, "w") as f:
            json.dump(tasks, f, indent=2, ensure_ascii=False)
        print(f"\nWrote {TEST_RAW_PATH}")


if __name__ == "__main__":
    main()
