#!/usr/bin/env python3
"""Test setup_scripts execution in a real browser against SuiteCRM.

For each modality task, this script:
1. Navigates to the start URL
2. Executes each setup_script via page.evaluate()
3. Takes a screenshot
4. Dumps the AXTree text
5. Reports success/failure

Usage:
    python scripts/test_setup_scripts_browser.py [--tasks 295,310,320,340]
"""

import json
import sys
import os
import argparse
import traceback
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TEST_RAW = REPO_ROOT / "stwebagentbench" / "test.raw.json"
OUTPUT_DIR = REPO_ROOT / ".policy_improvements" / "modality_test_screenshots"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", default="295,296,298,300,301,303,304,305,308,310,315,320,325,327,330,331,332,335,340,345,350,355,360,365,370",
                        help="Comma-separated task IDs to test (default: one per category + all URL types)")
    parser.add_argument("--all", action="store_true", help="Test all 80 tasks")
    parser.add_argument("--headless", action="store_true", default=True)
    args = parser.parse_args()

    from playwright.sync_api import sync_playwright

    # Load tasks
    with open(TEST_RAW) as f:
        all_tasks = json.load(f)
    modality_tasks = {t["task_id"]: t for t in all_tasks if 295 <= t.get("task_id", 0) <= 374}

    if args.all:
        task_ids = sorted(modality_tasks.keys())
    else:
        task_ids = [int(x) for x in args.tasks.split(",")]

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # SuiteCRM URL
    suitecrm_url = os.environ.get("WA_SUITECRM", "http://localhost:8080")

    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=args.headless)
        context = browser.new_context(viewport={"width": 1280, "height": 720})

        # Login to SuiteCRM (uses same approach as instance.py ui_login)
        page = context.new_page()
        print(f"Logging into SuiteCRM at {suitecrm_url}...")
        page.goto(suitecrm_url)
        page.wait_for_timeout(5000)

        try:
            page.get_by_label("Username").fill("user")
            page.get_by_label("Password").fill("bitnami")
            page.get_by_text("Log in").click()
            page.wait_for_timeout(8000)
            print(f"  Post-login URL: {page.url}")
        except Exception as e:
            print(f"  Login failed: {e}")
            print("  Continuing anyway (may already be logged in)...")
        page.close()

        for tid in task_ids:
            if tid not in modality_tasks:
                print(f"\nTask {tid}: NOT FOUND")
                continue

            task = modality_tasks[tid]
            cat = task.get("task_metadata", {}).get("category", "unknown")
            modality = task.get("task_metadata", {}).get("modality_class", "unknown")
            setup_scripts = task.get("setup_scripts", [])

            print(f"\n{'='*60}")
            print(f"Task {tid} [{modality} / {cat}]")
            print(f"Intent: {task['intent'][:80]}...")

            page = context.new_page()
            try:
                # Navigate to start URL
                start_url = task["start_url"].replace("__SUITECRM__", suitecrm_url)
                start_urls = start_url.split(" |AND| ")
                for i, url in enumerate(start_urls):
                    page.goto(url)
                    # Match task.py SPA wait: networkidle + fallback
                    try:
                        page.wait_for_load_state("networkidle", timeout=10000)
                    except Exception:
                        page.wait_for_timeout(3000)
                    page.wait_for_timeout(2000)  # extra SPA render time
                    if i < len(start_urls) - 1:
                        page = context.new_page()

                print(f"  Page URL: {page.url}")

                # Execute setup scripts
                for j, script in enumerate(setup_scripts):
                    try:
                        page.evaluate(f"() => {{ {script} }}")
                        print(f"  Script {j+1}/{len(setup_scripts)}: OK")
                    except Exception as e:
                        print(f"  Script {j+1}/{len(setup_scripts)}: FAILED - {e}")
                        results.append({"task_id": tid, "status": "SCRIPT_ERROR", "error": str(e)})
                        raise

                page.wait_for_timeout(1000)

                # Screenshot
                screenshot_path = OUTPUT_DIR / f"task_{tid}_{cat}.png"
                page.screenshot(path=str(screenshot_path))
                print(f"  Screenshot: {screenshot_path.name}")

                # Get AXTree text (simplified)
                try:
                    text = page.evaluate("() => document.body.innerText.substring(0, 2000)")
                    axtree_path = OUTPUT_DIR / f"task_{tid}_text.txt"
                    with open(axtree_path, "w") as f:
                        f.write(text)
                except Exception:
                    pass

                # Quick modality check for vision tasks
                if modality == "vision_advantage":
                    # Use AXTree snapshot for more accurate check
                    try:
                        ax_snap = page.accessibility.snapshot() or {}
                        ax_text = json.dumps(ax_snap)
                    except Exception:
                        ax_text = ""
                    body_text = page.evaluate("() => document.body.innerText") or ""

                    eval_cfg = task.get("eval", {})
                    ref = eval_cfg.get("reference_answers", {}) or {}
                    answer = ref.get("exact_match") or ""
                    if not answer and ref.get("must_include"):
                        answer = ref["must_include"][0] if isinstance(ref["must_include"], list) else ref["must_include"]

                    if answer and answer in ax_text:
                        print(f"  *** CRITICAL: answer '{answer}' found in AXTree (leaks to DOM agents)!")
                        results.append({"task_id": tid, "status": "AXTREE_LEAK", "answer": answer})
                    elif answer and answer in body_text:
                        # innerText doesn't respect aria-hidden; this is expected for tasks using aria-hidden
                        print(f"  Note: answer in innerText but NOT in AXTree (expected for aria-hidden)")
                        results.append({"task_id": tid, "status": "OK", "note": "innerText only, AXTree clean"})
                    else:
                        print(f"  Modality check: PASS (answer not in AXTree or innerText)")
                        results.append({"task_id": tid, "status": "OK"})
                else:
                    results.append({"task_id": tid, "status": "OK"})

            except Exception as e:
                if not any(r["task_id"] == tid for r in results):
                    results.append({"task_id": tid, "status": "ERROR", "error": str(e)})
                traceback.print_exc()
            finally:
                page.close()

        browser.close()

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    ok = sum(1 for r in results if r["status"] == "OK")
    errs = sum(1 for r in results if r["status"] in ("ERROR", "SCRIPT_ERROR"))
    leaks = sum(1 for r in results if r["status"] == "AXTREE_LEAK")
    print(f"Tested: {len(results)}, OK: {ok}, Errors: {errs}, AXTree leaks: {leaks}")

    for r in results:
        if r["status"] != "OK":
            print(f"  Task {r['task_id']}: {r['status']} - {r.get('error', r.get('answer', ''))}")

    # Save results
    results_path = OUTPUT_DIR / "test_results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {results_path}")


if __name__ == "__main__":
    main()
