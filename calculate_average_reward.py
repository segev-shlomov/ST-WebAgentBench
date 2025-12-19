#!/usr/bin/env python3
"""
Calculate the average total reward from all collected_data.json files in exp_1 folders.
"""

import json
import os
from pathlib import Path

def find_collected_data_files(base_path="data/STWebAgentBenchEnv/browsergym"):
    """Find all collected_data.json files in exp_1 folders."""
    base = Path(base_path)
    if not base.exists():
        print(f"Error: Directory {base_path} does not exist")
        return []

    files = list(base.glob("*/exp_1/collected_data.json"))
    return files

def extract_reward(file_path):
    """Extract total_reward from a collected_data.json file."""
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            if data and len(data) > 0:
                return data[0].get('total_reward', 0)
            return 0
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
        return None

def main():
    print("Searching for collected_data.json files in exp_1 folders...")
    files = find_collected_data_files()

    if not files:
        print("No files found.")
        return

    print(f"Found {len(files)} files.\n")

    rewards = []
    for file_path in sorted(files):
        reward = extract_reward(file_path)
        if reward is not None:
            task_name = file_path.parent.parent.name
            rewards.append(reward)
            print(f"{task_name}: reward = {reward}")

    if rewards:
        avg_reward = sum(rewards) / len(rewards)
        total_reward = sum(rewards)

        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Total files processed: {len(rewards)}")
        print(f"Total reward: {total_reward}")
        print(f"Average reward: {avg_reward:.4f}")
        print("=" * 60)
    else:
        print("No valid rewards found.")

if __name__ == "__main__":
    main()
