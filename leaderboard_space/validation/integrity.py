"""Cryptographic integrity layer for ST-WebAgentBench leaderboard submissions.

Generates tamper-evident evidence during evaluation:
- Code pinning: SHA256 of critical source files (evaluators, tasks, env)
- Trajectory hash chain: per-task hash binding actions + safety report + reward
- Manifest seal: deterministic hash of the entire integrity manifest
- HMAC signature: anti-forgery guarantee using a shared secret key

The leaderboard server compares these against known-good values to detect
modified evaluation code, tampered trajectories, or replayed submissions.
"""

import hashlib
import hmac as _hmac
import json
import logging
import os
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

BENCHMARK_VERSION = "1.0.0"

# Critical source files whose SHA256 must match known-good hashes on the server.
# Paths are relative to the project root.
_CODE_ARTIFACTS = {
    "evaluators_sha256": "stwebagentbench/evaluation_harness/evaluators.py",
    "task_config_sha256": "stwebagentbench/test.raw.json",
    "custom_env_sha256": "stwebagentbench/browser_env/custom_env.py",
    "helper_functions_sha256": "stwebagentbench/evaluation_harness/helper_functions.py",
}


@dataclass
class IntegrityManifest:
    """Cryptographic manifest generated during evaluation.

    Embeds hashes of all critical artifacts so the leaderboard server
    can detect any post-hoc tampering with results, code, or task definitions.
    """

    # Run identity
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    benchmark_version: str = BENCHMARK_VERSION
    timestamp_start: float = field(default_factory=time.time)
    timestamp_end: Optional[float] = None

    # Code integrity pins (populated by pin_code_artifacts)
    evaluators_sha256: str = ""
    task_config_sha256: str = ""
    custom_env_sha256: str = ""
    helper_functions_sha256: str = ""

    # Per-task trajectory hashes (task_id -> hash)
    task_hashes: Dict[int, str] = field(default_factory=dict)

    # Final seal over the entire manifest
    manifest_hash: str = ""

    # HMAC signature (requires ST_BENCH_SIGNING_KEY env var)
    hmac_signature: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "IntegrityManifest":
        return cls(**data)


# ---------------------------------------------------------------------------
# Hashing utilities
# ---------------------------------------------------------------------------


def compute_file_hash(filepath: str) -> str:
    """Compute SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_data_hash(data: Any) -> str:
    """Compute SHA256 of a JSON-serializable object using canonical form.

    Uses sorted keys and compact separators to ensure deterministic output
    regardless of dict ordering or whitespace.
    """
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Code pinning
# ---------------------------------------------------------------------------


def pin_code_artifacts(project_root: str) -> Dict[str, str]:
    """Compute SHA256 hashes of all critical source files.

    These are compared against known-good hashes on the leaderboard server.
    If any hash mismatches, the submission is flagged as using modified code.

    Args:
        project_root: Absolute path to the project root directory.

    Returns:
        Dict mapping hash field names to their SHA256 hex digests.
    """
    root = Path(project_root)
    hashes = {}
    for key, rel_path in _CODE_ARTIFACTS.items():
        full_path = root / rel_path
        if full_path.exists():
            hashes[key] = compute_file_hash(str(full_path))
        else:
            logger.warning("Code artifact not found: %s", full_path)
            hashes[key] = ""
    return hashes


# ---------------------------------------------------------------------------
# Trajectory hashing
# ---------------------------------------------------------------------------


def create_trajectory_hash(
    task_id: int,
    actions: List[dict],
    safety_report: List[dict],
    total_reward: float,
) -> str:
    """Create a hash for a single task's trajectory evidence.

    Binds the ordered action sequence, the full safety report, and
    the task reward cryptographically — any post-hoc edit to any
    component invalidates the hash.

    Args:
        task_id: The benchmark task identifier.
        actions: List of action dicts, each with 'action_type' and 'action_args'.
        safety_report: List of per-policy report dicts from the evaluator.
        total_reward: The task reward (0.0 or 1.0).

    Returns:
        SHA256 hex digest of the canonical JSON representation.
    """
    chain_data = {
        "task_id": task_id,
        "action_sequence": [
            {
                "step": i,
                "action_type": a.get("action_type", ""),
                "action_args": a.get("action_args", []),
            }
            for i, a in enumerate(actions)
        ],
        "safety_report": _normalize_safety_report(safety_report),
        "total_reward": total_reward,
    }
    return compute_data_hash(chain_data)


def _normalize_safety_report(report: List[dict]) -> List[dict]:
    """Extract only the hashable fields from safety report entries.

    Strips non-deterministic or implementation-specific fields while
    preserving all evaluation-relevant data.
    """
    normalized = []
    for entry in report:
        normalized.append({
            "violated": bool(entry.get("violated", False)),
            "dormant": bool(entry.get("dormant", False)),
            "violating_step": entry.get("violating_step"),
            "eval_type": entry.get("eval_type"),
        })
    return normalized


# ---------------------------------------------------------------------------
# Manifest seal
# ---------------------------------------------------------------------------


def seal_manifest(manifest: IntegrityManifest) -> str:
    """Compute the final seal over the entire manifest.

    Uses a deterministic hash. While this alone does not prevent
    recomputation by an adversary, it serves as a structural integrity
    check. The HMAC signature (see compute_hmac_signature) provides
    the actual anti-forgery guarantee.

    Args:
        manifest: The integrity manifest to seal.

    Returns:
        SHA256 hex digest of the manifest contents (excluding the seal
        and HMAC signature).
    """
    manifest_dict = manifest.to_dict()
    manifest_dict.pop("manifest_hash", None)
    manifest_dict.pop("hmac_signature", None)
    return compute_data_hash(manifest_dict)


# ---------------------------------------------------------------------------
# HMAC signing (anti-forgery)
# ---------------------------------------------------------------------------

# Environment variable name for the signing key (overrides the embedded default).
SIGNING_KEY_ENV_VAR = "ST_BENCH_SIGNING_KEY"


def compute_hmac_signature(manifest: IntegrityManifest, signing_key: str) -> str:
    """Compute HMAC-SHA256 over the manifest content.

    Signs the same content as seal_manifest but with a secret key,
    making it impossible to forge without knowing the key.

    Args:
        manifest: The integrity manifest to sign.
        signing_key: The shared secret key.

    Returns:
        HMAC-SHA256 hex digest.
    """
    manifest_dict = manifest.to_dict()
    manifest_dict.pop("manifest_hash", None)
    manifest_dict.pop("hmac_signature", None)
    canonical = json.dumps(manifest_dict, sort_keys=True, separators=(",", ":"), default=str)
    return _hmac.new(
        signing_key.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_hmac_signature(
    manifest: IntegrityManifest, signing_key: str
) -> bool:
    """Verify the HMAC signature on a manifest.

    Args:
        manifest: The manifest with hmac_signature field set.
        signing_key: The shared secret key.

    Returns:
        True if the signature is valid, False otherwise.
    """
    if not manifest.hmac_signature:
        return False
    expected = compute_hmac_signature(manifest, signing_key)
    return _hmac.compare_digest(manifest.hmac_signature, expected)


def finalize_manifest(manifest: IntegrityManifest) -> IntegrityManifest:
    """Set the end timestamp, compute the seal, and sign with HMAC.

    Call this after all tasks have been evaluated.

    If ST_BENCH_SIGNING_KEY is set in the environment, the manifest
    is HMAC-signed. Otherwise, hmac_signature is left empty (the
    leaderboard server will flag unsigned submissions).

    Args:
        manifest: The manifest to finalize.

    Returns:
        The same manifest with timestamp_end, manifest_hash, and
        optionally hmac_signature set.
    """
    manifest.timestamp_end = time.time()
    manifest.manifest_hash = seal_manifest(manifest)

    # Sign with HMAC — the Space always uses the env var secret
    signing_key = os.environ.get(SIGNING_KEY_ENV_VAR, "").strip()
    if signing_key:
        manifest.hmac_signature = compute_hmac_signature(manifest, signing_key)
        logger.info("Manifest HMAC-signed successfully")

    return manifest


def save_manifest(manifest: IntegrityManifest, output_path: str) -> None:
    """Write the integrity manifest to a JSON file."""
    with open(output_path, "w") as f:
        json.dump(manifest.to_dict(), f, indent=2)
    logger.info("Integrity manifest saved to %s", output_path)


def load_manifest(filepath: str) -> IntegrityManifest:
    """Load an integrity manifest from a JSON file."""
    with open(filepath, "r") as f:
        data = json.load(f)
    return IntegrityManifest.from_dict(data)
