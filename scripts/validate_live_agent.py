#!/usr/bin/env python3
"""Live agent validation for ST-WebAgentBench.

Runs the DemoAgent on representative tasks from CRM tiers and Modality
categories to validate end-to-end correctness of policies and evaluators.

Requirements:
    - SuiteCRM running (docker-compose or remote)
    - .env with WA_SUITECRM and OPENAI_API_KEY set
    - Package installed: make install

Usage:
    PYTHONPATH=. python3 scripts/validate_live_agent.py --category all
    PYTHONPATH=. python3 scripts/validate_live_agent.py --category crm
    PYTHONPATH=. python3 scripts/validate_live_agent.py --category modality
"""

import argparse
import json
import os
import sys
import warnings
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Suppress noisy warnings
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)

import gymnasium as gym
import browsergym.stwebagentbench

from st_bench_example import DemoAgentArgs, get_action_set

TASKS_PATH = Path("stwebagentbench/test.raw.json")

# ── Representative task sets ────────────────────────────────────────────────

TASK_SETS = {
    "crm_easy":        [235, 238, 242, 247, 252],
    "crm_medium":      [255, 260, 265, 270, 274],
    "crm_hard":        [275, 280, 285, 290, 294],
    "modality_ro":     [295, 310, 330, 350, 370],
    "modality_rw":     [297, 302, 307],
    "crm_extra":       [236, 241, 246, 256, 261, 276, 281, 286, 291, 296],
}

CATEGORIES = {
    "crm":      ["crm_easy", "crm_medium", "crm_hard", "crm_extra"],
    "modality": ["modality_ro", "modality_rw"],
    "all":      list(TASK_SETS.keys()),
}


def load_tasks_config():
    with open(TASKS_PATH) as f:
        return json.load(f)


def run_single_task(task_id, model_name, max_steps, headless):
    """Run agent on one task and return validation data."""
    task_name = f"browsergym/STWebAgentBenchEnv.{task_id}"
    action_set = get_action_set(multiaction=True)

    result = {
        "task_id": task_id,
        "task_name": task_name,
        "start_time": datetime.now().isoformat(),
        "loaded": False,
        "steps_executed": 0,
        "reward": 0.0,
        "safety_reports": [],
        "violated_policies": [],
        "dormant_policies": [],
        "errors": [],
        "policy_count_match": False,
    }

    try:
        env = gym.make(
            task_name,
            headless=headless,
            action_mapping=action_set.to_python_code,
            timeout=30000,
        )
    except Exception as e:
        result["errors"].append(f"env.make failed: {e}")
        return result

    try:
        obs, info = env.reset()
        result["loaded"] = True

        # Validate policy injection
        obs_policies = obs.get("policies", [])
        result["obs_policy_count"] = len(obs_policies)

        # Create agent
        agent = DemoAgentArgs(model_name=model_name).make_agent()

        done = False
        step = 0

        while not done and step < max_steps:
            step += 1
            new_obs = agent.obs_preprocessor(obs)
            action = agent.get_action(new_obs)

            env.chat.add_message("assistant", action)
            obs, reward, terminated, truncated, info = env.step(action)

            if "safety_report" in info:
                for report in info["safety_report"]:
                    result["safety_reports"].append(report)
                    if report.get("violated"):
                        result["violated_policies"].append(report)
                    if report.get("dormant"):
                        result["dormant_policies"].append(report)

            result["reward"] = reward
            done = terminated or truncated

        result["steps_executed"] = step

    except Exception as e:
        result["errors"].append(f"execution error: {e}")
    finally:
        try:
            env.close()
        except Exception:
            pass

    result["end_time"] = datetime.now().isoformat()
    return result


def validate_task_result(result, task_config):
    """Validate a single task result against expected behavior."""
    checks = []
    tid = result["task_id"]

    # Check 1: Task loaded
    checks.append({
        "check": "task_load",
        "passed": result["loaded"],
        "detail": "env.reset() succeeded" if result["loaded"] else f"Failed: {result['errors']}",
    })

    # Check 2: Agent ran at least 1 step
    checks.append({
        "check": "agent_interaction",
        "passed": result["steps_executed"] >= 1,
        "detail": f"{result['steps_executed']} steps executed",
    })

    # Check 3: Safety reports generated
    n_reports = len(result.get("safety_reports", []))
    n_policies = len(task_config.get("policies", []))

    # Safety reports are generated per-step at task validation, so they should
    # be present if the task completed. The final safety report from the last
    # step should have exactly n_policies entries.
    has_reports = n_reports > 0
    checks.append({
        "check": "evaluator_execution",
        "passed": has_reports,
        "detail": f"{n_reports} safety reports collected, {n_policies} policies expected",
    })

    # Check 4: No execution errors
    no_errors = len(result.get("errors", [])) == 0
    checks.append({
        "check": "no_errors",
        "passed": no_errors,
        "detail": "Clean execution" if no_errors else f"Errors: {result['errors']}",
    })

    # Check 5: Dormancy for read-only tasks
    is_readonly = tid in set(range(295, 375)) - {297, 302, 307}
    if is_readonly and n_reports > 0:
        consent_dormant = [
            r for r in result["safety_reports"]
            if r.get("policy", {}).get("policy_category") == "user_consent"
            and r.get("policy", {}).get("policy_template_id") == "ask_the_user"
            and r.get("dormant")
        ]
        consent_total = [
            r for r in result["safety_reports"]
            if r.get("policy", {}).get("policy_category") == "user_consent"
            and r.get("policy", {}).get("policy_template_id") == "ask_the_user"
        ]
        dormancy_ok = len(consent_dormant) == len(consent_total) if consent_total else True
        checks.append({
            "check": "dormancy_correctness",
            "passed": dormancy_ok,
            "detail": f"{len(consent_dormant)}/{len(consent_total)} consent policies dormant",
        })

    return checks


def run_validation(args):
    """Main validation loop."""
    print("=" * 70)
    print("  ST-WebAgentBench Live Agent Validation")
    print("=" * 70)
    print(f"  Model: {args.model_name}")
    print(f"  Max steps: {args.max_steps}")
    print(f"  Headless: {args.headless}")
    print(f"  Category: {args.category}")
    print()

    tasks_config = load_tasks_config()
    task_config_by_id = {t["task_id"]: t for t in tasks_config}

    # Determine which tasks to run
    task_sets_to_run = CATEGORIES.get(args.category, [args.category])
    task_ids = []
    for ts in task_sets_to_run:
        task_ids.extend(TASK_SETS.get(ts, []))
    task_ids = sorted(set(task_ids))

    print(f"  Tasks to validate: {len(task_ids)}")
    print(f"  Task IDs: {task_ids}")
    print()

    # Run all tasks
    all_results = []
    all_checks = defaultdict(list)

    for i, tid in enumerate(task_ids):
        print(f"  [{i+1}/{len(task_ids)}] Task {tid}...", end=" ", flush=True)

        result = run_single_task(tid, args.model_name, args.max_steps, args.headless)
        all_results.append(result)

        task_cfg = task_config_by_id.get(tid, {})
        checks = validate_task_result(result, task_cfg)

        status = "PASS" if all(c["passed"] for c in checks) else "ISSUES"
        n_violations = len(result.get("violated_policies", []))
        n_dormant = len(result.get("dormant_policies", []))
        print(f"steps={result['steps_executed']}, reward={result['reward']:.1f}, "
              f"violations={n_violations}, dormant={n_dormant}, {status}")

        for check in checks:
            all_checks[check["check"]].append(check["passed"])

        time.sleep(2)  # Brief pause between tasks

    # ── Report ──────────────────────────────────────────────────────────
    print()
    print("=" * 70)
    print("  Validation Summary")
    print("=" * 70)

    overall_pass = True
    for check_name, results in all_checks.items():
        passed = sum(results)
        total = len(results)
        status = "PASS" if passed == total else "WARN"
        if status == "WARN":
            overall_pass = False
        print(f"  {check_name:30s} {passed}/{total}  {status}")

    # Per-category metrics
    print()
    print("  Per-Category Breakdown:")
    for ts_name in task_sets_to_run:
        ts_ids = set(TASK_SETS.get(ts_name, []))
        ts_results = [r for r in all_results if r["task_id"] in ts_ids]
        if not ts_results:
            continue
        n = len(ts_results)
        avg_reward = sum(r["reward"] for r in ts_results) / n
        avg_violations = sum(len(r["violated_policies"]) for r in ts_results) / n
        avg_dormant = sum(len(r["dormant_policies"]) for r in ts_results) / n
        loaded = sum(1 for r in ts_results if r["loaded"])
        print(f"    {ts_name:20s} loaded={loaded}/{n}, avg_reward={avg_reward:.2f}, "
              f"avg_violations={avg_violations:.1f}, avg_dormant={avg_dormant:.1f}")

    # CRM Tier Differentiation
    print()
    print("  CRM Tier Differentiation:")
    for tier in ["crm_easy", "crm_medium", "crm_hard"]:
        ts_ids = set(TASK_SETS.get(tier, []))
        ts_results = [r for r in all_results if r["task_id"] in ts_ids]
        if not ts_results:
            continue
        n_policies_avg = sum(
            len(task_config_by_id.get(r["task_id"], {}).get("policies", []))
            for r in ts_results
        ) / len(ts_results)
        avg_violations = sum(len(r["violated_policies"]) for r in ts_results) / len(ts_results)
        print(f"    {tier:20s} avg_policies={n_policies_avg:.1f}, avg_violations={avg_violations:.1f}")

    # Save results
    output_dir = Path("data/validation_run")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

    # Serialize results (strip non-serializable fields from safety_reports)
    serializable_results = []
    for r in all_results:
        sr = {k: v for k, v in r.items() if k not in ("safety_reports", "violated_policies", "dormant_policies")}
        sr["n_safety_reports"] = len(r.get("safety_reports", []))
        sr["n_violated"] = len(r.get("violated_policies", []))
        sr["n_dormant"] = len(r.get("dormant_policies", []))
        serializable_results.append(sr)

    with open(output_path, "w") as f:
        json.dump(serializable_results, f, indent=2)
    print(f"\n  Results saved to: {output_path}")

    print()
    print("=" * 70)
    if overall_pass:
        print("  OVERALL: ALL CHECKS PASSED")
    else:
        print("  OVERALL: SOME CHECKS HAD WARNINGS — Review details above")
    print("=" * 70)

    return 0 if overall_pass else 1


def main():
    parser = argparse.ArgumentParser(description="Live agent validation for ST-WebAgentBench")
    parser.add_argument("--model_name", type=str, default="gpt-4o-mini",
                        help="LLM model name")
    parser.add_argument("--max_steps", type=int, default=15,
                        help="Max steps per task (reduced for validation speed)")
    parser.add_argument("--headless", type=bool, default=True,
                        help="Run browser headless")
    parser.add_argument("--category", type=str, default="all",
                        choices=["all", "crm", "modality", "crm_easy", "crm_medium",
                                 "crm_hard", "crm_extra", "modality_ro", "modality_rw"],
                        help="Task category to validate")
    args = parser.parse_args()
    sys.exit(run_validation(args))


if __name__ == "__main__":
    main()
