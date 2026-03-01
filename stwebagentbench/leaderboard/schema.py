"""Pydantic models for ST-WebAgentBench leaderboard submissions.

Defines the complete submission bundle schema including metadata,
per-task evidence, computed metrics, and integrity manifest.

Task/policy counts and safety dimensions are computed dynamically
from test.raw.json so constants auto-adapt when the benchmark grows.
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator

from stwebagentbench.leaderboard.integrity import BENCHMARK_VERSION

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Dynamic benchmark config — computed from test.raw.json at startup
# ---------------------------------------------------------------------------

_TASKS_DATA_PATH = Path(__file__).resolve().parent.parent / "test.raw.json"


def _load_benchmark_config() -> tuple:
    """Load task/policy counts and safety dimensions from test.raw.json."""
    if not _TASKS_DATA_PATH.exists():
        raise FileNotFoundError(
            f"test.raw.json not found at {_TASKS_DATA_PATH}. "
            "This file is required for benchmark configuration."
        )

    with open(_TASKS_DATA_PATH) as f:
        tasks = json.load(f)

    task_count = len(tasks)
    policy_count = sum(len(t.get("policies", [])) for t in tasks)

    dim_set = set()
    for t in tasks:
        for p in t.get("policies", []):
            cat = p.get("policy_category", "")
            if cat:
                dim_set.add(cat)

    safety_dims = sorted(dim_set)
    dim_display = {d: d.replace("_", " ").title().replace("And ", "& ") for d in safety_dims}

    # Extract actual task IDs (don't assume 0..N-1)
    task_ids = sorted(t["task_id"] for t in tasks)

    logger.info(
        "Loaded benchmark config: %d tasks, %d policies, %d dimensions",
        task_count, policy_count, len(safety_dims),
    )
    return task_count, policy_count, safety_dims, dim_display, task_ids


EXPECTED_TASK_COUNT, EXPECTED_POLICY_COUNT, SAFETY_DIMENSIONS, DIMENSION_DISPLAY, EXPECTED_TASK_IDS = (
    _load_benchmark_config()
)


# ---------------------------------------------------------------------------
# Per-step evidence
# ---------------------------------------------------------------------------


class ActionSummary(BaseModel):
    """Lightweight action record for server-side re-evaluation.

    Excludes screenshots, full DOM, and LLM reasoning (too large).
    Includes everything needed for offline evaluators.
    """

    step: int = Field(..., ge=0)
    action_type: str = Field(..., description="e.g. click, fill, goto, send_msg_to_user, answer")
    action_args: List[str] = Field(default_factory=list)
    element_text: str = Field("", description="From state_info, for ActionEvaluator matching")
    element_bid: str = Field("", description="From state_info, for CountAction/Sequence matching")
    observed_url: str = Field("", description="Page URL after this action")
    open_pages_urls: List[str] = Field(default_factory=list)
    timestamp: float = Field(..., description="Epoch seconds")


# ---------------------------------------------------------------------------
# Per-policy evidence
# ---------------------------------------------------------------------------


class PolicyReport(BaseModel):
    """Per-policy evaluation result within a task."""

    policy_index: int = Field(..., ge=0)
    policy_template_id: str
    policy_category: str
    source: str = Field(..., description="organization, user, or task")
    violated: bool
    dormant: bool
    violating_step: Optional[int] = None
    violating_action: Optional[str] = None
    eval_type: Optional[str] = None


# ---------------------------------------------------------------------------
# Per-task evidence
# ---------------------------------------------------------------------------


class TaskEvidence(BaseModel):
    """Evidence for a single task execution."""

    task_id: int = Field(..., ge=0)

    # Core results
    total_reward: float = Field(..., ge=0, le=1)
    satisfied_requirements: int = Field(0, ge=0)
    total_requirements: int = Field(1, ge=1)
    safety_report: List[PolicyReport]

    # Trajectory summary
    action_sequence: List[ActionSummary]
    visited_urls: List[str] = Field(default_factory=list)

    # Timing
    start_time: str
    end_time: str
    num_steps: int = Field(..., ge=0)

    # Hash binding (must match integrity manifest)
    trajectory_hash: str


# ---------------------------------------------------------------------------
# Aggregate metrics
# ---------------------------------------------------------------------------


class DimensionMetrics(BaseModel):
    """Per-safety-dimension aggregated metrics."""

    dimension: str
    failures: int = Field(..., ge=0)
    total_instances: int = Field(..., ge=0)
    active_instances: int = Field(..., ge=0)
    dormant_count: int = Field(..., ge=0)
    risk_ratio: float = Field(..., ge=0, le=1)
    active_risk_ratio: float = Field(..., ge=0, le=1)
    risk_tier: str  # low, medium, high
    active_risk_tier: str


class TierMetrics(BaseModel):
    """Per-difficulty-tier metrics (Easy/Medium/Hard CRM tasks)."""

    tier: str
    CR: float = Field(..., ge=0, le=1)
    CuP: float = Field(..., ge=0, le=1)
    semi_CR: float = Field(..., ge=0, le=1)
    semi_CuP: float = Field(..., ge=0, le=1)


class PerAppMetrics(BaseModel):
    """Per-application metrics."""

    app: str
    CR: float = Field(..., ge=0, le=1)
    CuP: float = Field(..., ge=0, le=1)
    semi_CR: float = Field(0, ge=0, le=1)
    semi_CuP: float = Field(0, ge=0, le=1)
    task_count: int = Field(..., ge=0)


class ClaimedMetrics(BaseModel):
    """Aggregate metrics claimed by the submitter.

    These are independently recomputed server-side from task_results.
    Any discrepancy flags the submission for review.
    """

    CR: float = Field(..., ge=0, le=1, description="Completion Rate")
    CuP: float = Field(..., ge=0, le=1, description="Completion under Policy")
    semi_CR: float = Field(..., ge=0, le=1, description="Partial Completion Rate")
    semi_CuP: float = Field(..., ge=0, le=1, description="Partial CuP")
    all_pass_at_k: Optional[float] = Field(None, ge=0, le=1)
    k: Optional[int] = Field(None, ge=1)


# ---------------------------------------------------------------------------
# Submission results (wraps all metric types)
# ---------------------------------------------------------------------------


class SubmissionResults(BaseModel):
    """All computed metrics for the submission."""

    metrics: ClaimedMetrics
    dimensions: List[DimensionMetrics]
    tiers: Optional[List[TierMetrics]] = None
    apps: Optional[List[PerAppMetrics]] = None
    tasks_evaluated: int = Field(..., ge=0)
    tasks_total: int = EXPECTED_TASK_COUNT
    policies_evaluated: int = Field(..., ge=0)


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------


class SubmissionMetadata(BaseModel):
    """Agent and team metadata for a leaderboard submission."""

    # Required
    agent_id: str = Field(..., min_length=1, max_length=128)
    model_name: str = Field(..., min_length=1, max_length=256)
    team: str = Field(..., min_length=1, max_length=256)
    code_repository_url: str = Field(
        ...,
        min_length=1,
        description="Public GitHub/GitLab/HuggingFace repository URL",
    )
    contact_email: str = Field(
        ...,
        min_length=1,
        description="Contact email for verification (not displayed publicly)",
    )

    # Optional
    paper_url: Optional[str] = None
    agent_framework: Optional[str] = None
    model_family: Optional[str] = None
    is_open_source: Optional[bool] = None
    is_open_weights: Optional[bool] = None
    cost_per_task_usd: Optional[float] = Field(None, ge=0)
    total_cost_usd: Optional[float] = Field(None, ge=0)
    hardware: Optional[str] = None
    num_runs: int = Field(1, ge=1)
    uses_vision: Optional[bool] = None
    max_steps: Optional[int] = Field(None, ge=1)
    description: Optional[str] = Field(None, max_length=1000)

    @field_validator("agent_id")
    @classmethod
    def validate_agent_id(cls, v: str) -> str:
        if not re.match(r"^[a-zA-Z0-9_\-\.]+$", v):
            raise ValueError(
                "agent_id must contain only alphanumeric characters, "
                "hyphens, underscores, and dots"
            )
        return v

    @field_validator("code_repository_url")
    @classmethod
    def validate_repo_url(cls, v: str) -> str:
        valid_prefixes = (
            "https://github.com/",
            "https://gitlab.com/",
            "https://huggingface.co/",
            "https://bitbucket.org/",
        )
        if not any(v.startswith(p) for p in valid_prefixes):
            raise ValueError(
                "code_repository_url must be a public GitHub, GitLab, "
                "HuggingFace, or Bitbucket URL"
            )
        return v


# ---------------------------------------------------------------------------
# Integrity section
# ---------------------------------------------------------------------------


class IntegritySection(BaseModel):
    """Cryptographic integrity data from the evaluation run."""

    run_id: str
    benchmark_version: str = BENCHMARK_VERSION
    timestamp_start: float
    timestamp_end: Optional[float] = None
    evaluators_sha256: str
    task_config_sha256: str
    custom_env_sha256: str
    helper_functions_sha256: str
    task_hashes: dict  # task_id (str key in JSON) -> SHA256
    manifest_hash: str
    hmac_signature: Optional[str] = Field(
        None,
        description="HMAC-SHA256 signature (requires ST_BENCH_SIGNING_KEY)",
    )


# ---------------------------------------------------------------------------
# Top-level submission
# ---------------------------------------------------------------------------


class Submission(BaseModel):
    """Complete leaderboard submission bundle.

    Contains metadata, per-task evidence, computed metrics, and
    cryptographic integrity data.
    """

    schema_version: str = Field("1.0", description="Submission schema version")
    benchmark_version: str = BENCHMARK_VERSION
    submission_date: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    metadata: SubmissionMetadata
    results: SubmissionResults
    task_evidence: List[TaskEvidence]
    integrity: IntegritySection

    @field_validator("submission_date")
    @classmethod
    def validate_date(cls, v: str) -> str:
        # Ensure the date can be parsed
        try:
            datetime.fromisoformat(v)
        except ValueError as e:
            raise ValueError(f"submission_date must be ISO 8601 format: {e}") from e
        return v
