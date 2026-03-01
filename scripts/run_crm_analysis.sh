#!/usr/bin/env bash
# Run the demo agent on all CRM (SuiteCRM) tasks.
# Trajectories are saved to data/STWebAgentBenchEnv/browsergym/ (git-ignored).
#
# Usage:
#   bash scripts/run_crm_analysis.sh              # Run all 170 CRM tasks
#   bash scripts/run_crm_analysis.sh core          # Run only tasks 47-76
#   bash scripts/run_crm_analysis.sh advanced      # Run only tasks 235-294
#   bash scripts/run_crm_analysis.sh modality      # Run only tasks 295-374

set -e
cd "$(dirname "$0")/.."

MODEL="${MODEL:-gpt-4o-mini}"
GROUP="${1:-all}"

echo "=== ST-WebAgentBench CRM Task Analysis Runner ==="
echo "Model: $MODEL"
echo "Group: $GROUP"
echo ""

run_range() {
    local label="$1"
    local range="$2"
    echo "--- Running $label (tasks $range) ---"
    python st_bench_example_loop.py \
        --specific_tasks_range "$range" \
        --model_name "$MODEL" \
        --headless True
    echo "--- Finished $label ---"
    echo ""
}

case "$GROUP" in
    core)
        run_range "Core CRM Tasks" "47-76"
        ;;
    advanced)
        run_range "Advanced Easy CRM Tasks" "235-254"
        run_range "Advanced Medium CRM Tasks" "255-274"
        run_range "Advanced Hard CRM Tasks" "275-294"
        ;;
    modality)
        run_range "Modality CRM Tasks" "295-374"
        ;;
    all)
        run_range "Core CRM Tasks" "47-76"
        run_range "Advanced Easy CRM Tasks" "235-254"
        run_range "Advanced Medium CRM Tasks" "255-274"
        run_range "Advanced Hard CRM Tasks" "275-294"
        run_range "Modality CRM Tasks" "295-374"
        ;;
    *)
        echo "Unknown group: $GROUP. Use: core, advanced, modality, or all"
        exit 1
        ;;
esac

echo "=== All runs complete ==="
echo "Trajectories saved to: data/STWebAgentBenchEnv/browsergym/"
echo ""
echo "Next step: run scripts/extract_screenshots.py to pull key screenshots"
