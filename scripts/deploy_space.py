#!/usr/bin/env python3
"""Deploy leaderboard_space to HuggingFace Space with auto-synced data.

Automatically:
1. Copies canonical test.raw.json from stwebagentbench/ to leaderboard_space/data/
2. Computes canonical code hashes and writes canonical_hashes.json
3. Commits changes
4. Deploys via git subtree push

Usage:
    python scripts/deploy_space.py            # Deploy (commits + pushes)
    python scripts/deploy_space.py --check    # Check sync status only (no deploy)
"""

import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_TASKS = PROJECT_ROOT / "stwebagentbench" / "test.raw.json"
DST_TASKS = PROJECT_ROOT / "leaderboard_space" / "data" / "test.raw.json"
HASHES_FILE = PROJECT_ROOT / "leaderboard_space" / "data" / "canonical_hashes.json"

CODE_ARTIFACTS = {
    "evaluators_sha256": PROJECT_ROOT / "stwebagentbench" / "evaluation_harness" / "evaluators.py",
    "task_config_sha256": PROJECT_ROOT / "stwebagentbench" / "test.raw.json",
    "custom_env_sha256": PROJECT_ROOT / "stwebagentbench" / "browser_env" / "custom_env.py",
    "helper_functions_sha256": PROJECT_ROOT / "stwebagentbench" / "evaluation_harness" / "helper_functions.py",
}


def compute_file_hash(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def sync_tasks() -> bool:
    """Copy test.raw.json to leaderboard_space/data/. Returns True if changed."""
    if not SRC_TASKS.exists():
        print(f"ERROR: {SRC_TASKS} not found")
        sys.exit(1)

    DST_TASKS.parent.mkdir(parents=True, exist_ok=True)

    if DST_TASKS.exists():
        src_hash = compute_file_hash(SRC_TASKS)
        dst_hash = compute_file_hash(DST_TASKS)
        if src_hash == dst_hash:
            print("  test.raw.json: in sync")
            return False

    shutil.copy2(SRC_TASKS, DST_TASKS)
    print("  test.raw.json: UPDATED (copied from stwebagentbench/)")
    return True


def sync_hashes() -> bool:
    """Compute canonical hashes and write to JSON. Returns True if changed."""
    new_hashes = {}
    for key, path in CODE_ARTIFACTS.items():
        if not path.exists():
            print(f"  WARNING: {path} not found, skipping {key}")
            new_hashes[key] = ""
        else:
            new_hashes[key] = compute_file_hash(path)

    new_content = {"1.0.0": new_hashes}

    if HASHES_FILE.exists():
        with open(HASHES_FILE) as f:
            old_content = json.load(f)
        if old_content == new_content:
            print("  canonical_hashes.json: in sync")
            return False

    HASHES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(HASHES_FILE, "w") as f:
        json.dump(new_content, f, indent=2)
        f.write("\n")
    print("  canonical_hashes.json: UPDATED")
    return True


def main():
    check_only = "--check" in sys.argv

    print("Syncing leaderboard_space data...")
    tasks_changed = sync_tasks()
    hashes_changed = sync_hashes()

    if check_only:
        if tasks_changed or hashes_changed:
            print("\nData was out of sync — files have been updated.")
            print("Run without --check to deploy.")
            sys.exit(1)
        else:
            print("\nAll data in sync.")
            sys.exit(0)

    if tasks_changed or hashes_changed:
        print("\nCommitting synced data...")
        subprocess.run(["git", "add", "-f", str(DST_TASKS)], check=True, cwd=PROJECT_ROOT)
        subprocess.run(["git", "add", "-f", str(HASHES_FILE)], check=True, cwd=PROJECT_ROOT)
        subprocess.run(["git", "add", str(PROJECT_ROOT / "leaderboard_space")], check=True, cwd=PROJECT_ROOT)
        subprocess.run([
            "git", "commit", "-m",
            "Auto-sync test.raw.json and canonical_hashes.json for Space deploy"
        ], check=True, cwd=PROJECT_ROOT)
    else:
        print("\nNo data changes needed.")

    print("\nDeploying to HuggingFace Space...")
    # Split leaderboard_space/ into a temp branch and force-push to Space
    subprocess.run(
        ["git", "subtree", "split", "--prefix", "leaderboard_space", "-b", "space-deploy"],
        check=True, cwd=PROJECT_ROOT,
    )
    subprocess.run(
        ["git", "push", "space", "space-deploy:main", "--force"],
        check=True, cwd=PROJECT_ROOT,
    )
    subprocess.run(
        ["git", "branch", "-D", "space-deploy"],
        check=True, cwd=PROJECT_ROOT,
    )
    print("\nDeploy complete.")


if __name__ == "__main__":
    main()
