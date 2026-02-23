"""CLI tool to package ST-WebAgentBench evaluation results into a leaderboard submission.

Usage (single run):
    python -m stwebagentbench.leaderboard.submit \\
        --results-dir data/STWebAgentBenchEnv/browsergym \\
        --agent-id "my-agent-v1" \\
        --model-name "gpt-4o-2024-08-06" \\
        --team "MIT NLP Lab" \\
        --code-url "https://github.com/org/repo" \\
        --contact-email "team@mit.edu" \\
        --output submission.json

Usage (multi-run for all-pass@k):
    python -m stwebagentbench.leaderboard.submit \\
        --results-dirs run1/ run2/ run3/ \\
        --agent-id "my-agent-v1" \\
        --model-name "gpt-4o" \\
        --team "MIT NLP Lab" \\
        --code-url "https://github.com/org/repo" \\
        --contact-email "team@mit.edu" \\
        --output submission.json
"""

import argparse
import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from stwebagentbench.leaderboard.integrity import (
    BENCHMARK_VERSION,
    IntegrityManifest,
    create_trajectory_hash,
    finalize_manifest,
    pin_code_artifacts,
)
from stwebagentbench.leaderboard.schema import (
    ActionSummary,
    ClaimedMetrics,
    DimensionMetrics,
    IntegritySection,
    PerAppMetrics,
    PolicyReport,
    Submission,
    SubmissionMetadata,
    SubmissionResults,
    TaskEvidence,
    TierMetrics,
)
from stwebagentbench.result_analysis.analyze import (
    compute_category_safety,
    compute_completion_rates,
    compute_tier_metrics,
    fill_and_save_agent_full_res,
    fill_and_save_multi_run_res,
)

logger = logging.getLogger(__name__)

FULL_TASKS_PATH = "stwebagentbench/test.raw.json"


# ---------------------------------------------------------------------------
# Action string parsing
# ---------------------------------------------------------------------------

# Matches patterns like: click('a51') or fill('b12', 'search term')
_ACTION_RE = re.compile(r"^(\w+)\((.*)?\)$", re.DOTALL)
# Matches individual quoted arguments (handles escaped quotes)
_ARG_RE = re.compile(r"""['"]([^'"]*?)['"]""")


def parse_action_string(action_str: str) -> Tuple[str, List[str]]:
    """Parse a BrowserGym action string into (action_type, action_args).

    Examples:
        >>> parse_action_string("click('a51')")
        ('click', ['a51'])
        >>> parse_action_string("fill('b12', 'hello world')")
        ('fill', ['b12', 'hello world'])
        >>> parse_action_string("goto('http://example.com')")
        ('goto', ['http://example.com'])
        >>> parse_action_string("noop()")
        ('noop', [])
    """
    action_str = action_str.strip()
    m = _ACTION_RE.match(action_str)
    if not m:
        return action_str, []
    action_type = m.group(1)
    args_str = m.group(2) or ""
    args = _ARG_RE.findall(args_str)
    return action_type, args


# ---------------------------------------------------------------------------
# Evidence extraction from collected data
# ---------------------------------------------------------------------------


def extract_task_evidence(
    task_id: int,
    collected_data: dict,
    tasks_data: List[dict],
) -> Optional[TaskEvidence]:
    """Extract TaskEvidence from a single task's collected_data.json.

    Args:
        task_id: The benchmark task identifier.
        collected_data: Parsed contents of collected_data.json.
        tasks_data: Full task definitions from test.raw.json.

    Returns:
        TaskEvidence if extraction succeeds, None otherwise.
    """
    if isinstance(collected_data, list):
        collected_data = collected_data[0]

    # Find canonical task config for policy metadata
    task_config = None
    for t in tasks_data:
        if t["task_id"] == task_id:
            task_config = t
            break
    if task_config is None:
        logger.warning("Task %d not found in task definitions", task_id)
        return None

    canonical_policies = task_config.get("policies", [])

    # Extract safety report from task_info_gt (final evaluation)
    task_info_gt = collected_data.get("task_info_gt", {})
    safety_report_raw = task_info_gt.get("safety_report", [])

    # Build per-policy reports
    policy_reports = []
    for idx, canonical_policy in enumerate(canonical_policies):
        report_entry = safety_report_raw[idx] if idx < len(safety_report_raw) else {}
        policy_reports.append(PolicyReport(
            policy_index=idx,
            policy_template_id=canonical_policy.get("policy_template_id", ""),
            policy_category=canonical_policy.get("policy_category", ""),
            source=canonical_policy.get("source", ""),
            violated=bool(report_entry.get("violated", False)),
            dormant=bool(report_entry.get("dormant", False)),
            violating_step=report_entry.get("violating_step"),
            violating_action=report_entry.get("violating_action"),
            eval_type=report_entry.get("eval_type"),
        ))

    # Build action sequence from steps
    steps = collected_data.get("steps", [])
    action_sequence = []
    visited_urls = set()

    # Use task-level start_time as a baseline for per-step timestamps
    task_start_iso = collected_data.get("start_time", "")
    task_start_epoch = _iso_to_epoch(task_start_iso) or time.time()

    for step_idx, step_data in enumerate(steps):
        action_str = step_data.get("action", "")
        action_type, action_args = parse_action_string(action_str)

        # Extract element info from LLM output if available
        llm_data = step_data.get("llm_reasoning") or {}
        if isinstance(llm_data, dict):
            element_text = llm_data.get("element_text", "")
            element_bid = llm_data.get("element_bid", "")
        else:
            element_text = ""
            element_bid = ""

        # Infer element_bid from action_args when not available
        # (first arg to click/fill/hover/select_option is typically the bid)
        if not element_bid and action_args and action_type in (
            "click", "fill", "hover", "dblclick", "select_option",
            "focus", "clear", "check", "uncheck",
        ):
            element_bid = action_args[0]

        # Extract URL from step data (various possible keys)
        observed_url = (
            step_data.get("url", "")
            or step_data.get("observed_url", "")
            or step_data.get("page_url", "")
        )
        open_pages = step_data.get("open_pages_urls", [])

        # For goto actions, the URL is in the args
        if not observed_url and action_type == "goto" and action_args:
            observed_url = action_args[0]

        if observed_url:
            visited_urls.add(observed_url)
        for u in open_pages:
            visited_urls.add(u)

        # Use step timestamp if available, else estimate from task start
        step_timestamp = step_data.get("timestamp", task_start_epoch + step_idx)

        action_sequence.append(ActionSummary(
            step=step_data.get("step", len(action_sequence)),
            action_type=action_type,
            action_args=action_args,
            element_text=element_text,
            element_bid=element_bid,
            observed_url=observed_url,
            open_pages_urls=open_pages,
            timestamp=step_timestamp,
        ))

    total_reward = collected_data.get("total_reward", 0)
    satisfied = task_info_gt.get("satisfied_requirements", 0)
    total_req = task_info_gt.get("total_requirements", 1)

    # Compute trajectory hash
    actions_for_hash = [
        {"action_type": a.action_type, "action_args": a.action_args}
        for a in action_sequence
    ]
    safety_for_hash = [
        {
            "violated": pr.violated,
            "dormant": pr.dormant,
            "violating_step": pr.violating_step,
            "eval_type": pr.eval_type,
        }
        for pr in policy_reports
    ]
    trajectory_hash = create_trajectory_hash(
        task_id, actions_for_hash, safety_for_hash, total_reward,
    )

    return TaskEvidence(
        task_id=task_id,
        total_reward=total_reward,
        satisfied_requirements=satisfied,
        total_requirements=total_req,
        safety_report=policy_reports,
        action_sequence=action_sequence,
        visited_urls=sorted(visited_urls),
        start_time=collected_data.get("start_time", ""),
        end_time=collected_data.get("end_time", ""),
        num_steps=len(steps),
        trajectory_hash=trajectory_hash,
    )


# ---------------------------------------------------------------------------
# Aggregate metrics from analyze.py DataFrame
# ---------------------------------------------------------------------------


def extract_dimension_metrics(df) -> List[DimensionMetrics]:
    """Extract per-dimension metrics from the analyze.py DataFrame."""
    from stwebagentbench.result_analysis.analyze import (
        categorize_risk,
        compute_category_safety,
    )

    cat_df = compute_category_safety(df)
    dimensions = []
    for _, row in cat_df.iterrows():
        dimensions.append(DimensionMetrics(
            dimension=row["categories"],
            failures=int(row["failures"]),
            total_instances=int(row["total_instances"]),
            active_instances=int(row["active_instances"]),
            dormant_count=int(row["dormant_count"]),
            risk_ratio=float(row["risk_ratio"]),
            active_risk_ratio=float(row["active_risk_ratio"]),
            risk_tier=str(row["risk"]),
            active_risk_tier=str(row["active_risk"]),
        ))
    return dimensions


def extract_tier_metrics(df) -> Optional[List[TierMetrics]]:
    """Extract per-tier metrics from the analyze.py DataFrame."""
    tier_results = compute_tier_metrics(df)
    if not tier_results:
        return None
    tiers = []
    for tier_name, metrics in tier_results.items():
        tiers.append(TierMetrics(
            tier=tier_name,
            CR=metrics["CR"],
            CuP=metrics["CuP"],
            semi_CR=metrics["semi_CR"],
            semi_CuP=metrics["semi_CuP"],
        ))
    return tiers


def extract_app_metrics(df) -> Optional[List[PerAppMetrics]]:
    """Extract per-application metrics from the analyze.py DataFrame."""
    apps = []
    for app_name in df["app_id"].unique():
        app_df = df[df["app_id"] == app_name]
        unique_tasks = app_df.drop_duplicates(subset="task_id")
        total = unique_tasks.shape[0]
        if total == 0:
            continue
        cr = round(unique_tasks["task_success"].sum() / total, 3)
        cup = round(unique_tasks["success_under_policy"].sum() / total, 3)
        apps.append(PerAppMetrics(app=app_name, CR=cr, CuP=cup, task_count=total))
    return apps if apps else None


# ---------------------------------------------------------------------------
# Main build function
# ---------------------------------------------------------------------------


def build_submission(
    results_dir: str,
    agent_id: str,
    metadata_kwargs: dict,
    project_root: str = ".",
    full_tasks_path: str = FULL_TASKS_PATH,
    multi_run_dirs: Optional[List[str]] = None,
) -> Submission:
    """Build a complete submission from evaluation results.

    Loads raw results using existing analyze.py functions, extracts
    per-task evidence, computes all metrics, and assembles the
    submission bundle with integrity manifest.

    Args:
        results_dir: Path to single-run results directory.
        agent_id: Agent identifier string.
        metadata_kwargs: Dict of SubmissionMetadata fields.
        project_root: Path to the project root (for code pinning).
        full_tasks_path: Path to test.raw.json.
        multi_run_dirs: List of run directories for multi-run submissions.

    Returns:
        Submission object ready for serialization.

    Raises:
        ValueError: If no results are found.
    """
    # Load task definitions
    with open(full_tasks_path, "r") as f:
        tasks_data = json.load(f)

    # Initialize integrity manifest
    manifest = IntegrityManifest()
    code_hashes = pin_code_artifacts(project_root)
    manifest.evaluators_sha256 = code_hashes.get("evaluators_sha256", "")
    manifest.task_config_sha256 = code_hashes.get("task_config_sha256", "")
    manifest.custom_env_sha256 = code_hashes.get("custom_env_sha256", "")
    manifest.helper_functions_sha256 = code_hashes.get("helper_functions_sha256", "")

    # Load results into DataFrame (reuse existing analysis code)
    if multi_run_dirs:
        df = fill_and_save_multi_run_res(multi_run_dirs, agent_id, full_tasks_path)
        num_runs = len(multi_run_dirs)
    else:
        df = fill_and_save_agent_full_res(results_dir, agent_id, full_tasks_path)
        num_runs = 1

    if df is None or df.empty:
        raise ValueError("No results found in the specified directory")

    # Compute aggregate metrics
    cr, cup, semi_cr, semi_cup = compute_completion_rates(df)
    dimensions = extract_dimension_metrics(df)
    tiers = extract_tier_metrics(df)
    apps = extract_app_metrics(df)

    # Compute all-pass@k for multi-run
    all_pass_at_k = None
    k = None
    if num_runs > 1:
        from stwebagentbench.result_analysis.analyze import compute_all_pass_at_k
        all_pass_at_k, k, _ = compute_all_pass_at_k(df)

    # Extract per-task evidence
    task_evidence_list = []
    results_path = Path(results_dir)
    subfolders = sorted(
        [sf for sf in results_path.iterdir() if sf.is_dir()],
        key=lambda x: _extract_task_id_from_name(x.name),
    )

    for subfolder in subfolders:
        json_files = list(subfolder.rglob("collected_data.json"))
        if not json_files:
            continue
        json_file = json_files[0]
        try:
            with open(json_file, "r") as f:
                data = json.load(f)
            task_id = _extract_task_id_from_name(subfolder.name)
            if task_id < 0:
                continue
            evidence = extract_task_evidence(task_id, data, tasks_data)
            if evidence:
                task_evidence_list.append(evidence)
                manifest.task_hashes[str(task_id)] = evidence.trajectory_hash
        except (json.JSONDecodeError, Exception) as e:
            logger.warning("Failed to process %s: %s", json_file, e)

    # Finalize manifest
    manifest = finalize_manifest(manifest)

    # Build claimed metrics
    claimed = ClaimedMetrics(
        CR=cr,
        CuP=cup,
        semi_CR=semi_cr,
        semi_CuP=semi_cup,
        all_pass_at_k=all_pass_at_k,
        k=k,
    )

    # Build results
    total_policies = sum(len(te.safety_report) for te in task_evidence_list)
    results = SubmissionResults(
        metrics=claimed,
        dimensions=dimensions,
        tiers=tiers,
        apps=apps,
        tasks_evaluated=len(task_evidence_list),
        policies_evaluated=total_policies,
    )

    # Build metadata
    metadata_kwargs["agent_id"] = agent_id
    metadata_kwargs["num_runs"] = num_runs
    metadata = SubmissionMetadata(**metadata_kwargs)

    # Build integrity section
    integrity = IntegritySection(
        run_id=manifest.run_id,
        benchmark_version=manifest.benchmark_version,
        timestamp_start=manifest.timestamp_start,
        timestamp_end=manifest.timestamp_end,
        evaluators_sha256=manifest.evaluators_sha256,
        task_config_sha256=manifest.task_config_sha256,
        custom_env_sha256=manifest.custom_env_sha256,
        helper_functions_sha256=manifest.helper_functions_sha256,
        task_hashes=manifest.task_hashes,
        manifest_hash=manifest.manifest_hash,
        hmac_signature=manifest.hmac_signature or None,
    )

    return Submission(
        metadata=metadata,
        results=results,
        task_evidence=task_evidence_list,
        integrity=integrity,
    )


def _extract_task_id_from_name(name: str) -> int:
    """Extract numeric task ID from a folder name like 'STWebAgentBenchEnv.235'."""
    match = re.search(r"\d+$", name)
    if match:
        return int(match.group())
    return -1


def _iso_to_epoch(iso_str: str) -> Optional[float]:
    """Convert ISO 8601 datetime string to epoch seconds, or None on failure."""
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.timestamp()
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main():
    parser = argparse.ArgumentParser(
        description="Package ST-WebAgentBench results into a leaderboard submission",
    )
    parser.add_argument(
        "--results-dir", type=str,
        help="Path to single-run results directory",
    )
    parser.add_argument(
        "--results-dirs", nargs="+", type=str,
        help="Multiple run directories for all-pass@k",
    )
    parser.add_argument("--agent-id", type=str, required=True)
    parser.add_argument("--model-name", type=str, required=True)
    parser.add_argument("--team", type=str, required=True)
    parser.add_argument("--code-url", type=str, required=True,
                        help="Public code repository URL")
    parser.add_argument("--contact-email", type=str, required=True,
                        help="Contact email for verification")

    # Optional metadata
    parser.add_argument("--paper-url", type=str, default=None)
    parser.add_argument("--agent-framework", type=str, default=None)
    parser.add_argument("--model-family", type=str, default=None)
    parser.add_argument("--is-open-source", action="store_true", default=None)
    parser.add_argument("--is-open-weights", action="store_true", default=None)
    parser.add_argument("--cost-per-task", type=float, default=None)
    parser.add_argument("--total-cost", type=float, default=None)
    parser.add_argument("--hardware", type=str, default=None)
    parser.add_argument("--uses-vision", action="store_true", default=None)
    parser.add_argument("--max-steps", type=int, default=None)
    parser.add_argument("--description", type=str, default=None)

    # Paths
    parser.add_argument("--project-root", type=str, default=".",
                        help="Project root directory for code pinning")
    parser.add_argument("--tasks-file", type=str, default=FULL_TASKS_PATH)
    parser.add_argument("--output", type=str, default="submission.json")
    parser.add_argument("--validate-only", action="store_true",
                        help="Only validate, do not create submission file")

    args = parser.parse_args()

    if not args.results_dir and not args.results_dirs:
        parser.error("Either --results-dir or --results-dirs is required")

    metadata_kwargs = {
        "model_name": args.model_name,
        "team": args.team,
        "code_repository_url": args.code_url,
        "contact_email": args.contact_email,
        "paper_url": args.paper_url,
        "agent_framework": args.agent_framework,
        "model_family": args.model_family,
        "is_open_source": args.is_open_source if args.is_open_source else None,
        "is_open_weights": args.is_open_weights if args.is_open_weights else None,
        "cost_per_task_usd": args.cost_per_task,
        "total_cost_usd": args.total_cost,
        "hardware": args.hardware,
        "uses_vision": args.uses_vision if args.uses_vision else None,
        "max_steps": args.max_steps,
        "description": args.description,
    }

    submission = build_submission(
        results_dir=args.results_dir or args.results_dirs[0],
        agent_id=args.agent_id,
        metadata_kwargs=metadata_kwargs,
        project_root=args.project_root,
        full_tasks_path=args.tasks_file,
        multi_run_dirs=args.results_dirs,
    )

    if args.validate_only:
        from stwebagentbench.leaderboard.validate import (
            recompute_metrics_from_evidence,
            validate_submission,
        )
        with open(args.tasks_file, "r") as f:
            tasks_data = json.load(f)
        errors = validate_submission(submission, tasks_data=tasks_data)
        metric_errors = recompute_metrics_from_evidence(submission)
        errors.extend(metric_errors)
        if errors:
            print(f"Validation failed with {len(errors)} error(s):")
            for e in errors:
                print(f"  - {e}")
        else:
            print("Validation passed.")
            print(f"  CR: {submission.results.metrics.CR}")
            print(f"  CuP: {submission.results.metrics.CuP}")
            print(f"  Tasks: {submission.results.tasks_evaluated}")
            print(f"  Policies: {submission.results.policies_evaluated}")
    else:
        with open(args.output, "w") as f:
            f.write(submission.model_dump_json(indent=2))
        print(f"Submission written to {args.output}")
        print(f"  Agent: {submission.metadata.agent_id}")
        print(f"  CR: {submission.results.metrics.CR}")
        print(f"  CuP: {submission.results.metrics.CuP}")
        print(f"  Tasks: {submission.results.tasks_evaluated}/{submission.results.tasks_total}")
        print(f"  Policies: {submission.results.policies_evaluated}")
        print(f"  Run ID: {submission.integrity.run_id}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
