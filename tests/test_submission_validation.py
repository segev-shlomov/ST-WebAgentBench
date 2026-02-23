"""Validate both test submissions against the full leaderboard pipeline.

The legitimate submission (AWM paper results) should pass structural checks
with at most minor metric rounding discrepancies.

The adversarial submission embeds 10 attack vectors — every one should be caught.
"""

import json
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
LEGIT_PATH = TESTS_DIR / "test_submission_legitimate.json"
ADV_PATH = TESTS_DIR / "test_submission_adversarial.json"
TASKS_PATH = TESTS_DIR.parent / "stwebagentbench" / "test.raw.json"

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def legit_data():
    with open(LEGIT_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def adv_data():
    with open(ADV_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def tasks_data():
    with open(TASKS_PATH) as f:
        return json.load(f)


@pytest.fixture(scope="module")
def legit_submission(legit_data):
    from stwebagentbench.leaderboard.schema import Submission
    return Submission(**legit_data)


@pytest.fixture(scope="module")
def adv_submission(adv_data):
    """Adversarial submission — may fail Pydantic validation entirely."""
    from stwebagentbench.leaderboard.schema import Submission
    try:
        return Submission(**adv_data)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# LEGITIMATE SUBMISSION TESTS
# ---------------------------------------------------------------------------


class TestLegitimateSubmission:
    """The AWM-paper-based submission should pass the pipeline."""

    def test_pydantic_schema_validates(self, legit_data):
        """Legitimate submission must parse cleanly through Pydantic."""
        from stwebagentbench.leaderboard.schema import Submission
        sub = Submission(**legit_data)
        assert sub.metadata.agent_id == "AWM-agent-v1"
        assert sub.results.metrics.CR > 0
        assert sub.results.metrics.CuP > 0

    def test_has_all_295_tasks(self, legit_submission):
        task_ids = {te.task_id for te in legit_submission.task_evidence}
        assert len(task_ids) == 295

    def test_cup_does_not_exceed_cr(self, legit_submission):
        m = legit_submission.results.metrics
        assert m.CuP <= m.CR + 0.001

    def test_semi_cup_does_not_exceed_semi_cr(self, legit_submission):
        m = legit_submission.results.metrics
        assert m.semi_CuP <= m.semi_CR + 0.001

    def test_structural_validation_passes(self, legit_submission, tasks_data):
        from stwebagentbench.leaderboard.validate import validate_submission
        errors = validate_submission(legit_submission, tasks_data=tasks_data)
        # Allow only minor warnings, no hard structural errors
        hard_errors = [e for e in errors if "mismatch" in e.lower()
                       and "metric" not in e.lower()]
        assert len(hard_errors) == 0, f"Unexpected structural errors: {hard_errors}"

    def test_metric_recomputation_consistent(self, legit_submission):
        from stwebagentbench.leaderboard.validate import recompute_metrics_from_evidence
        discrepancies = recompute_metrics_from_evidence(legit_submission)
        # Filter out dormant+violated warnings (the generator can produce some)
        metric_discrepancies = [d for d in discrepancies
                                if "mismatch" in d.lower()
                                and "CR" in d or "CuP" in d or "risk" in d.lower()]
        assert len(metric_discrepancies) == 0, \
            f"Metric recomputation found issues: {metric_discrepancies}"

    def test_trajectory_hashes_valid(self, legit_submission):
        """Every task's trajectory hash should match the integrity manifest."""
        for te in legit_submission.task_evidence:
            task_key = str(te.task_id)
            manifest_hash = legit_submission.integrity.task_hashes.get(task_key)
            assert manifest_hash is not None, f"Task {te.task_id}: missing from manifest"
            assert te.trajectory_hash == manifest_hash, \
                f"Task {te.task_id}: hash mismatch"

    def test_anomaly_detection_clean(self, legit_submission):
        """Legitimate submission should have few or no anomaly flags."""
        from stwebagentbench.leaderboard.validate import detect_anomalies
        flags = detect_anomalies(legit_submission)
        # Allow timing flags (simulated timestamps may not be perfect)
        critical_flags = [f for f in flags if "zero violations" in f.lower()
                          or "dormancy ratio" in f.lower()
                          or "answer" in f.lower()]
        assert len(critical_flags) == 0, f"Unexpected critical anomalies: {critical_flags}"

    def test_metrics_near_paper_results(self, legit_submission):
        """Metrics should be close to the paper's AWM results."""
        m = legit_submission.results.metrics
        assert abs(m.CR - 0.34) < 0.02, f"CR={m.CR} too far from paper (0.34)"
        assert abs(m.CuP - 0.20) < 0.02, f"CuP={m.CuP} too far from paper (0.20)"

    def test_has_six_safety_dimensions(self, legit_submission):
        dims = {d.dimension for d in legit_submission.results.dimensions}
        from stwebagentbench.leaderboard.schema import SAFETY_DIMENSIONS
        assert dims == set(SAFETY_DIMENSIONS)

    def test_code_hashes_are_real(self, legit_submission):
        """Integrity section should have real (non-empty) code hashes."""
        assert len(legit_submission.integrity.evaluators_sha256) == 64
        assert len(legit_submission.integrity.task_config_sha256) == 64
        assert len(legit_submission.integrity.custom_env_sha256) == 64
        assert len(legit_submission.integrity.helper_functions_sha256) == 64


# ---------------------------------------------------------------------------
# ADVERSARIAL SUBMISSION TESTS
# ---------------------------------------------------------------------------


class TestAdversarialSubmission:
    """The adversarial submission should be caught by multiple layers."""

    def test_attack_1_cup_exceeds_cr(self, adv_data):
        """Attack #8: CuP (0.85) > CR (0.80) — impossible."""
        metrics = adv_data["results"]["metrics"]
        assert metrics["CuP"] > metrics["CR"], \
            "Adversarial test setup: CuP should exceed CR"

    def test_attack_1_detected_by_structural_validation(self, adv_data):
        """CuP > CR should be caught."""
        from stwebagentbench.leaderboard.schema import Submission
        try:
            sub = Submission(**adv_data)
        except Exception:
            return  # Pydantic rejects it outright — that's fine too

        from stwebagentbench.leaderboard.validate import validate_submission
        errors = validate_submission(sub)
        cup_errors = [e for e in errors if "CuP" in e and "CR" in e]
        assert len(cup_errors) > 0, \
            "Should detect CuP > CR impossibility"

    def test_attack_2_tampered_code_hashes(self, adv_data):
        """Attack #2: Fake evaluators_sha256 — should not match real hashes."""
        from tests.generate_test_submissions import REAL_CODE_HASHES
        for key in REAL_CODE_HASHES:
            assert adv_data["integrity"][key] != REAL_CODE_HASHES[key], \
                f"Test setup: {key} should differ from real"

    def test_attack_2_detected_with_canonical_hashes(self, adv_data):
        """Tampered code hashes caught when canonical hashes are provided."""
        from stwebagentbench.leaderboard.schema import Submission
        from tests.generate_test_submissions import REAL_CODE_HASHES
        try:
            sub = Submission(**adv_data)
        except Exception:
            return

        from stwebagentbench.leaderboard.validate import validate_submission
        errors = validate_submission(sub, canonical_hashes=REAL_CODE_HASHES)
        hash_errors = [e for e in errors if "integrity" in e.lower()]
        assert len(hash_errors) > 0, "Should detect tampered code hashes"

    def test_attack_5_missing_tasks(self, adv_data):
        """Attack #5: Only 290 tasks submitted (missing 5)."""
        assert len(adv_data["task_evidence"]) == 290

    def test_attack_5_detected_by_structural_validation(self, adv_data):
        """Missing tasks should be caught."""
        from stwebagentbench.leaderboard.schema import Submission
        try:
            sub = Submission(**adv_data)
        except Exception:
            return

        from stwebagentbench.leaderboard.validate import validate_submission
        errors = validate_submission(sub)
        missing_errors = [e for e in errors if "missing" in e.lower() and "task" in e.lower()]
        assert len(missing_errors) > 0, "Should detect missing tasks"

    def test_attack_6_xss_in_description(self, adv_data):
        """Attack #6: XSS in description should be sanitized."""
        desc = adv_data["metadata"]["description"]
        assert "<img" in desc.lower() or "onerror" in desc.lower(), \
            "Test setup: description should contain XSS"

    def test_attack_6_detected_by_sanitization(self, adv_data):
        """XSS in description caught by sanitization."""
        from stwebagentbench.leaderboard.schema import Submission
        try:
            sub = Submission(**adv_data)
        except Exception:
            return

        from stwebagentbench.leaderboard.validate import validate_submission
        errors = validate_submission(sub)
        xss_errors = [e for e in errors if "unsafe" in e.lower()]
        assert len(xss_errors) > 0, "Should detect XSS in metadata"

    def test_attack_7_timing_anomalies(self, adv_data):
        """Attack #7: 295 tasks in 10 minutes — impossibly fast."""
        from stwebagentbench.leaderboard.schema import Submission
        try:
            sub = Submission(**adv_data)
        except Exception:
            return

        from stwebagentbench.leaderboard.validate import detect_anomalies
        flags = detect_anomalies(sub)
        timing_flags = [f for f in flags if "step" in f.lower() or "0.5s" in f.lower()]
        assert len(timing_flags) > 0, "Should detect impossibly fast timing"

    def test_attack_3_dormancy_anomaly(self, adv_data):
        """Attack #3/#4: >95% dormancy should be flagged."""
        from stwebagentbench.leaderboard.schema import Submission
        try:
            sub = Submission(**adv_data)
        except Exception:
            return

        from stwebagentbench.leaderboard.validate import detect_anomalies
        flags = detect_anomalies(sub)
        dorm_flags = [f for f in flags if "dormancy" in f.lower()]
        assert len(dorm_flags) > 0, "Should detect abnormal dormancy ratio"

    def test_attack_9_empty_urls(self, adv_data):
        """Attack #9: Empty visited_urls flagged."""
        from stwebagentbench.leaderboard.schema import Submission
        try:
            sub = Submission(**adv_data)
        except Exception:
            return

        from stwebagentbench.leaderboard.validate import detect_anomalies
        flags = detect_anomalies(sub)
        url_flags = [f for f in flags if "visited url" in f.lower() or "no visited" in f.lower()]
        assert len(url_flags) > 0, "Should detect missing visited URLs"

    def test_attack_10_answer_action_anomaly(self, adv_data):
        """Attack #10: 80% answer actions flagged."""
        from stwebagentbench.leaderboard.schema import Submission
        try:
            sub = Submission(**adv_data)
        except Exception:
            return

        from stwebagentbench.leaderboard.validate import detect_anomalies
        flags = detect_anomalies(sub)
        answer_flags = [f for f in flags if "answer" in f.lower()]
        assert len(answer_flags) > 0, "Should detect answer action anomaly"

    def test_attack_1_metric_inflation_detected(self, adv_data):
        """Attack #1: Claimed CR=0.80 but evidence shows all succeed — recompute catches it."""
        from stwebagentbench.leaderboard.schema import Submission
        try:
            sub = Submission(**adv_data)
        except Exception:
            return

        from stwebagentbench.leaderboard.validate import recompute_metrics_from_evidence
        discrepancies = recompute_metrics_from_evidence(sub)
        # The adversarial submission claims CR=0.80 but only 290 tasks, all with reward=1.0
        # Recomputed: 290/290=1.0 or if missing tasks counted as 0: 290/295 ≈ 0.983
        # Either way, 0.80 != actual
        cr_disc = [d for d in discrepancies if "CR mismatch" in d]
        assert len(cr_disc) > 0, \
            f"Should detect inflated CR. All discrepancies: {discrepancies}"

    def test_anti_gaming_incompleteness(self, adv_data):
        """Anti-gaming layer should reject incomplete submission."""
        from stwebagentbench.leaderboard.schema import Submission
        try:
            sub = Submission(**adv_data)
        except Exception:
            return

        from stwebagentbench.leaderboard.validate import validate_anti_gaming
        issues = validate_anti_gaming(sub, submission_history=[])
        completeness = [i for i in issues if "295" in i]
        assert len(completeness) > 0, "Should reject incomplete submission"

    def test_adversarial_total_attacks_caught(self, adv_data):
        """At least 5 distinct attack vectors should be caught."""
        from stwebagentbench.leaderboard.schema import Submission
        try:
            sub = Submission(**adv_data)
        except Exception:
            # Pydantic rejection counts as 1 caught
            return

        from stwebagentbench.leaderboard.validate import (
            validate_submission, recompute_metrics_from_evidence,
            detect_anomalies, validate_anti_gaming,
        )
        from tests.generate_test_submissions import REAL_CODE_HASHES

        all_issues = []
        all_issues.extend(validate_submission(sub, canonical_hashes=REAL_CODE_HASHES))
        all_issues.extend(recompute_metrics_from_evidence(sub))
        all_issues.extend(detect_anomalies(sub))
        all_issues.extend(validate_anti_gaming(sub, submission_history=[]))

        assert len(all_issues) >= 5, \
            f"Only caught {len(all_issues)} issues (expected >=5): {all_issues}"


# ---------------------------------------------------------------------------
# HMAC SIGNING TESTS
# ---------------------------------------------------------------------------


class TestHMACSigning:
    """Test HMAC signing and verification for anti-forgery."""

    TEST_KEY = "test-signing-key-for-unit-tests"

    def test_hmac_signature_computed_with_key(self, legit_data):
        """When signing key is set, HMAC should be computable."""
        from stwebagentbench.leaderboard.integrity import (
            IntegrityManifest,
            compute_hmac_signature,
        )
        manifest = IntegrityManifest(
            run_id=legit_data["integrity"]["run_id"],
            benchmark_version=legit_data["integrity"]["benchmark_version"],
            timestamp_start=legit_data["integrity"]["timestamp_start"],
            timestamp_end=legit_data["integrity"]["timestamp_end"],
            evaluators_sha256=legit_data["integrity"]["evaluators_sha256"],
            task_config_sha256=legit_data["integrity"]["task_config_sha256"],
            custom_env_sha256=legit_data["integrity"]["custom_env_sha256"],
            helper_functions_sha256=legit_data["integrity"]["helper_functions_sha256"],
            task_hashes=legit_data["integrity"]["task_hashes"],
        )
        sig = compute_hmac_signature(manifest, self.TEST_KEY)
        assert len(sig) == 64  # SHA256 hex digest
        assert sig != legit_data["integrity"]["manifest_hash"]  # HMAC != plain hash

    def test_hmac_verification_succeeds_with_correct_key(self, legit_data):
        """HMAC verification should pass with the correct key."""
        from stwebagentbench.leaderboard.integrity import (
            IntegrityManifest,
            compute_hmac_signature,
            verify_hmac_signature,
        )
        manifest = IntegrityManifest(
            run_id=legit_data["integrity"]["run_id"],
            benchmark_version=legit_data["integrity"]["benchmark_version"],
            timestamp_start=legit_data["integrity"]["timestamp_start"],
            timestamp_end=legit_data["integrity"]["timestamp_end"],
            evaluators_sha256=legit_data["integrity"]["evaluators_sha256"],
            task_config_sha256=legit_data["integrity"]["task_config_sha256"],
            custom_env_sha256=legit_data["integrity"]["custom_env_sha256"],
            helper_functions_sha256=legit_data["integrity"]["helper_functions_sha256"],
            task_hashes=legit_data["integrity"]["task_hashes"],
        )
        manifest.hmac_signature = compute_hmac_signature(manifest, self.TEST_KEY)
        assert verify_hmac_signature(manifest, self.TEST_KEY)

    def test_hmac_verification_fails_with_wrong_key(self, legit_data):
        """HMAC verification should fail with a wrong key."""
        from stwebagentbench.leaderboard.integrity import (
            IntegrityManifest,
            compute_hmac_signature,
            verify_hmac_signature,
        )
        manifest = IntegrityManifest(
            run_id=legit_data["integrity"]["run_id"],
            benchmark_version=legit_data["integrity"]["benchmark_version"],
            timestamp_start=legit_data["integrity"]["timestamp_start"],
            timestamp_end=legit_data["integrity"]["timestamp_end"],
            evaluators_sha256=legit_data["integrity"]["evaluators_sha256"],
            task_config_sha256=legit_data["integrity"]["task_config_sha256"],
            custom_env_sha256=legit_data["integrity"]["custom_env_sha256"],
            helper_functions_sha256=legit_data["integrity"]["helper_functions_sha256"],
            task_hashes=legit_data["integrity"]["task_hashes"],
        )
        manifest.hmac_signature = compute_hmac_signature(manifest, self.TEST_KEY)
        assert not verify_hmac_signature(manifest, "wrong-key")

    def test_hmac_verification_fails_with_tampered_data(self, legit_data):
        """HMAC should fail if manifest data is tampered after signing."""
        from stwebagentbench.leaderboard.integrity import (
            IntegrityManifest,
            compute_hmac_signature,
            verify_hmac_signature,
        )
        manifest = IntegrityManifest(
            run_id=legit_data["integrity"]["run_id"],
            benchmark_version=legit_data["integrity"]["benchmark_version"],
            timestamp_start=legit_data["integrity"]["timestamp_start"],
            timestamp_end=legit_data["integrity"]["timestamp_end"],
            evaluators_sha256=legit_data["integrity"]["evaluators_sha256"],
            task_config_sha256=legit_data["integrity"]["task_config_sha256"],
            custom_env_sha256=legit_data["integrity"]["custom_env_sha256"],
            helper_functions_sha256=legit_data["integrity"]["helper_functions_sha256"],
            task_hashes=legit_data["integrity"]["task_hashes"],
        )
        manifest.hmac_signature = compute_hmac_signature(manifest, self.TEST_KEY)
        # Tamper with the data after signing
        manifest.evaluators_sha256 = "0" * 64
        assert not verify_hmac_signature(manifest, self.TEST_KEY)

    def test_validation_rejects_missing_hmac_when_key_set(self, legit_data):
        """When server has a signing key, unsigned submissions should be rejected."""
        from stwebagentbench.leaderboard.schema import Submission
        sub = Submission(**legit_data)

        # Import from Space's validation module
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "leaderboard_space"))
        from validation.validate import validate_submission

        errors = validate_submission(sub, signing_key=self.TEST_KEY)
        hmac_errors = [e for e in errors if "HMAC" in e or "hmac" in e]
        assert len(hmac_errors) > 0, \
            f"Should reject unsigned submission when key is set. Errors: {errors}"

    def test_validation_accepts_valid_hmac(self, legit_data):
        """When HMAC is correct, no HMAC errors should be raised."""
        import copy
        from stwebagentbench.leaderboard.integrity import (
            IntegrityManifest,
            compute_hmac_signature,
        )

        # Sign the manifest with our test key
        data = copy.deepcopy(legit_data)
        manifest = IntegrityManifest(
            run_id=data["integrity"]["run_id"],
            benchmark_version=data["integrity"]["benchmark_version"],
            timestamp_start=data["integrity"]["timestamp_start"],
            timestamp_end=data["integrity"]["timestamp_end"],
            evaluators_sha256=data["integrity"]["evaluators_sha256"],
            task_config_sha256=data["integrity"]["task_config_sha256"],
            custom_env_sha256=data["integrity"]["custom_env_sha256"],
            helper_functions_sha256=data["integrity"]["helper_functions_sha256"],
            task_hashes=data["integrity"]["task_hashes"],
        )
        data["integrity"]["hmac_signature"] = compute_hmac_signature(manifest, self.TEST_KEY)

        from stwebagentbench.leaderboard.schema import Submission
        sub = Submission(**data)

        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "leaderboard_space"))
        from validation.validate import validate_submission

        errors = validate_submission(sub, signing_key=self.TEST_KEY)
        hmac_errors = [e for e in errors if "HMAC" in e or "hmac" in e]
        assert len(hmac_errors) == 0, \
            f"Should accept valid HMAC. HMAC errors: {hmac_errors}"

    def test_no_hmac_enforcement_without_key(self, legit_data):
        """When no signing key is set, HMAC verification should be skipped."""
        from stwebagentbench.leaderboard.schema import Submission
        sub = Submission(**legit_data)

        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "leaderboard_space"))
        from validation.validate import validate_submission

        # No signing_key passed — should not complain about HMAC
        errors = validate_submission(sub, signing_key=None)
        hmac_errors = [e for e in errors if "HMAC" in e or "hmac" in e]
        assert len(hmac_errors) == 0, \
            f"Should not enforce HMAC without key. Errors: {hmac_errors}"


# ---------------------------------------------------------------------------
# Gradio app UI validation (lightweight)
# ---------------------------------------------------------------------------


try:
    import gradio
    HAS_GRADIO = True
except ImportError:
    HAS_GRADIO = False


@pytest.mark.skipif(not HAS_GRADIO, reason="gradio not installed")
class TestGradioAppValidation:
    """Test the Gradio app's validate_upload function."""

    def test_legit_json_passes_upload_validation(self, tmp_path, legit_data):
        """Legitimate submission passes the full 5-layer UI validation."""
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "leaderboard_space"))

        from leaderboard_space.app import validate_upload_full

        # Write to a temp file (mimicking Gradio file upload)
        tmp_file = tmp_path / "submission.json"
        tmp_file.write_text(json.dumps(legit_data))

        class FakeFile:
            name = str(tmp_file)

        status, data, report = validate_upload_full(FakeFile())
        assert status in ("verified", "flagged"), f"Should pass validation, got: {status}\n{report}"
        assert data is not None

    def test_adversarial_json_fails_upload_validation(self, tmp_path, adv_data):
        """Adversarial submission should fail the full 5-layer UI validation."""
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "leaderboard_space"))

        from leaderboard_space.app import validate_upload_full

        tmp_file = tmp_path / "submission.json"
        tmp_file.write_text(json.dumps(adv_data))

        class FakeFile:
            name = str(tmp_file)

        status, data, report = validate_upload_full(FakeFile())
        assert status == "rejected", f"Should reject adversarial submission, got: {status}\n{report}"
        assert data is None
