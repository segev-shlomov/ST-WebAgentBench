#!/usr/bin/env python3
"""
Extract first and last screenshots from collected_data.json files for CRM tasks
and save them as PNG files in .task_analysis/tasks/{group}/screenshots/.

Run from project root after agent runs:
    python scripts/extract_screenshots.py
"""

import json
import os
import base64
import numpy as np
from pathlib import Path

try:
    from PIL import Image
    import io
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("Warning: Pillow not installed. Install with: pip install Pillow")
    print("Will try to save raw base64 data instead.")


PROJECT_ROOT = Path(__file__).parent.parent
DATA_ROOT = PROJECT_ROOT / "data" / "STWebAgentBenchEnv" / "browsergym"
ANALYSIS_ROOT = PROJECT_ROOT / ".task_analysis" / "tasks"


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
    return "group_other"


def save_screenshot_from_array(screenshot_data, path: Path):
    """Save screenshot from base64 string or numpy array to PNG."""
    if not HAS_PIL:
        return False

    try:
        if isinstance(screenshot_data, str):
            # Base64 encoded PNG
            img_bytes = base64.b64decode(screenshot_data)
            img = Image.open(io.BytesIO(img_bytes))
        elif isinstance(screenshot_data, list):
            # RGB numpy array stored as nested list
            arr = np.array(screenshot_data, dtype=np.uint8)
            if arr.ndim == 3:
                img = Image.fromarray(arr)
            else:
                return False
        else:
            return False

        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(path))
        return True
    except Exception as e:
        print(f"  Error saving screenshot: {e}")
        return False


def extract_for_task(task_dir: Path, task_id: int):
    """Extract first and last screenshots for a task's most recent experiment."""
    # Find the latest exp_ directory
    exp_dirs = sorted(task_dir.glob("exp_*"), key=lambda d: int(d.name.split("_")[1]))
    if not exp_dirs:
        return False

    exp_dir = exp_dirs[-1]  # Use most recent run
    data_file = exp_dir / "collected_data.json"

    if not data_file.exists():
        return False

    try:
        with open(data_file) as f:
            data = json.load(f)
    except Exception as e:
        print(f"  Error reading {data_file}: {e}")
        return False

    group = get_group(task_id)
    screenshots_dir = ANALYSIS_ROOT / group / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)

    saved = 0

    # Try to get initial screenshot
    initial_obs = data.get("initial_observation", {})
    if isinstance(initial_obs, dict):
        screenshot = initial_obs.get("screenshot") or initial_obs.get("screenshot_base64")
        if screenshot:
            out_path = screenshots_dir / f"task_{task_id:03d}_initial.png"
            if not out_path.exists():
                if save_screenshot_from_array(screenshot, out_path):
                    saved += 1

    # Try to get final screenshot from last step
    steps = data.get("steps", [])
    if steps:
        last_step = steps[-1]
        for key in ["screenshot", "screenshot_base64", "observation"]:
            obs = last_step.get(key)
            if isinstance(obs, dict):
                obs = obs.get("screenshot") or obs.get("screenshot_base64")
            if obs:
                out_path = screenshots_dir / f"task_{task_id:03d}_final.png"
                if not out_path.exists():
                    if save_screenshot_from_array(obs, out_path):
                        saved += 1
                break

    return saved > 0


def main():
    if not DATA_ROOT.exists():
        print(f"Data directory not found: {DATA_ROOT}")
        print("Run the agent first: bash scripts/run_crm_analysis.sh")
        return

    # Find all CRM task directories
    task_dirs = []
    for d in DATA_ROOT.iterdir():
        if d.name.startswith("STWebAgentBenchEnv."):
            try:
                task_id = int(d.name.split(".")[1])
            except (IndexError, ValueError):
                continue
            # Only CRM tasks
            if (47 <= task_id <= 76) or (235 <= task_id <= 374):
                task_dirs.append((task_id, d))

    task_dirs.sort(key=lambda x: x[0])
    print(f"Found {len(task_dirs)} CRM task result directories")

    extracted = 0
    skipped = 0
    errors = 0

    for task_id, task_dir in task_dirs:
        print(f"  Task {task_id}...", end=" ")
        try:
            result = extract_for_task(task_dir, task_id)
            if result:
                print("✓")
                extracted += 1
            else:
                print("(no screenshots)")
                skipped += 1
        except Exception as e:
            print(f"ERROR: {e}")
            errors += 1

    print(f"\nDone: {extracted} extracted, {skipped} skipped, {errors} errors")
    print(f"Screenshots saved to: {ANALYSIS_ROOT}/{{group}}/screenshots/")


if __name__ == "__main__":
    main()
