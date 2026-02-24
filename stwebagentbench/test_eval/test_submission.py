"""Tests for the leaderboard submission pipeline.

Covers: schema validation, integrity hashing, metric recomputation,
input sanitization, anti-gaming controls, and action parsing.
"""

import json
import time

import pytest

from stwebagentbench.leaderboard.integrity import (
    BENCHMARK_VERSION,
    IntegrityManifest,
    compute_data_hash,
    compute_file_hash,
    create_trajectory_hash,
    finalize_manifest,
    seal_manifest,
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
from stwebagentbench.leaderboard.submit import parse_action_string
from stwebagentbench.leaderboard.validate import (
    detect_anomalies,
    is_safe_string,
    recompute_metrics_from_evidence,
    validate_anti_gaming,
    validate_submission,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_policy_report(index, violated=False, dormant=False):
    return PolicyReport(
        policy_index=index,
        policy_template_id="test_policy",
        policy_category="user_consent",
        source="organization",
        violated=violated,
        dormant=dormant,
    )


def _make_task_evidence(task_id, reward=1.0, violated_indices=None):
    violated_indices = violated_indices or set()
    reports = [
        _make_policy_report(i, violated=(i in violated_indices))
        for i in range(3)
    ]
    actions = [ActionSummary(
        step=0, action_type="click", action_args=["a1"],
        observed_url="http://example.com", timestamp=time.time(),
    )]
    return TaskEvidence(
        task_id=task_id,
        total_reward=reward,
        safety_report=reports,
        action_sequence=actions,
        visited_urls=["http://example.com"],
        start_time="2026-01-01T00:00:00+00:00",
        end_time="2026-01-01T00:01:00+00:00",
        num_steps=1,
        trajectory_hash="fakehash",
    )


def _make_minimal_submission(
    task_count=3,
    cr=0.667,
    cup=0.333,
    task_rewards=None,
    violated_tasks=None,
):
    """Create a minimal valid Submission for testing."""
    violated_tasks = violated_tasks or set()
    task_rewards = task_rewards or {i: 1.0 if i < 2 else 0.0 for i in range(task_count)}

    evidence = []
    for i in range(task_count):
        violated = {0} if i in violated_tasks else set()
        evidence.append(_make_task_evidence(
            task_id=i,
            reward=task_rewards.get(i, 0.0),
            violated_indices=violated,
        ))

    manifest = IntegrityManifest()
    for te in evidence:
        manifest.task_hashes[str(te.task_id)] = te.trajectory_hash
    manifest = finalize_manifest(manifest)

    return Submission(
        metadata=SubmissionMetadata(
            agent_id="test-agent",
            model_name="test-model",
            team="Test Team",
            code_repository_url="https://github.com/test/repo",
            contact_email="test@example.com",
        ),
        results=SubmissionResults(
            metrics=ClaimedMetrics(CR=cr, CuP=cup, semi_CR=cr, semi_CuP=cup),
            dimensions=[DimensionMetrics(
                dimension="user_consent",
                failures=len(violated_tasks),
                total_instances=task_count * 3,
                active_instances=task_count * 3,
                dormant_count=0,
                risk_ratio=round(len(violated_tasks) / (task_count * 3), 3) if task_count > 0 else 0,
                active_risk_ratio=round(len(violated_tasks) / (task_count * 3), 3) if task_count > 0 else 0,
                risk_tier="low",
                active_risk_tier="low",
            )],
            tasks_evaluated=task_count,
            policies_evaluated=task_count * 3,
        ),
        task_evidence=evidence,
        integrity=IntegritySection(
            run_id=manifest.run_id,
            timestamp_start=manifest.timestamp_start,
            timestamp_end=manifest.timestamp_end,
            evaluators_sha256="abc",
            task_config_sha256="def",
            custom_env_sha256="ghi",
            helper_functions_sha256="jkl",
            task_hashes=manifest.task_hashes,
            manifest_hash=manifest.manifest_hash,
        ),
    )


# ---------------------------------------------------------------------------
# Integrity tests
# ---------------------------------------------------------------------------


class TestIntegrity:

    def test_compute_data_hash_deterministic(self):
        data = {"b": 2, "a": 1}
        h1 = compute_data_hash(data)
        h2 = compute_data_hash({"a": 1, "b": 2})
        assert h1 == h2, "Hashes should be identical regardless of key order"

    def test_compute_data_hash_different_data(self):
        h1 = compute_data_hash({"a": 1})
        h2 = compute_data_hash({"a": 2})
        assert h1 != h2

    def test_trajectory_hash_changes_on_violation_flip(self):
        actions = [{"action_type": "click", "action_args": ["a1"]}]
        report_pass = [{"violated": False, "dormant": False, "violating_step": None, "eval_type": None}]
        report_fail = [{"violated": True, "dormant": False, "violating_step": 0, "eval_type": "is_url_match"}]

        h1 = create_trajectory_hash(0, actions, report_pass, 1.0)
        h2 = create_trajectory_hash(0, actions, report_fail, 1.0)
        assert h1 != h2, "Flipping a violation should change the hash"

    def test_trajectory_hash_changes_on_reward(self):
        actions = [{"action_type": "click", "action_args": ["a1"]}]
        report = [{"violated": False, "dormant": False, "violating_step": None, "eval_type": None}]

        h1 = create_trajectory_hash(0, actions, report, 1.0)
        h2 = create_trajectory_hash(0, actions, report, 0.0)
        assert h1 != h2, "Changing reward should change the hash"

    def test_manifest_seal_changes_on_modification(self):
        m = IntegrityManifest()
        m.task_hashes["0"] = "abc"
        m = finalize_manifest(m)
        seal1 = m.manifest_hash

        m2 = IntegrityManifest(
            run_id=m.run_id,
            timestamp_start=m.timestamp_start,
            timestamp_end=m.timestamp_end,
        )
        m2.task_hashes["0"] = "xyz"  # Modified
        m2 = finalize_manifest(m2)
        seal2 = m2.manifest_hash

        assert seal1 != seal2

    def test_compute_file_hash(self):
        """Test that compute_file_hash works on a real file."""
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("hello world")
            path = f.name
        h = compute_file_hash(path)
        assert len(h) == 64  # SHA256 hex digest
        import os
        os.unlink(path)


# ---------------------------------------------------------------------------
# Action parsing tests
# ---------------------------------------------------------------------------


class TestActionParsing:

    def test_simple_click(self):
        t, a = parse_action_string("click('a51')")
        assert t == "click"
        assert a == ["a51"]

    def test_fill_two_args(self):
        t, a = parse_action_string("fill('b12', 'hello world')")
        assert t == "fill"
        assert a == ["b12", "hello world"]

    def test_goto(self):
        t, a = parse_action_string("goto('http://example.com')")
        assert t == "goto"
        assert a == ["http://example.com"]

    def test_noop(self):
        t, a = parse_action_string("noop()")
        assert t == "noop"
        assert a == []

    def test_send_msg_to_user(self):
        t, a = parse_action_string("send_msg_to_user('Should I proceed?')")
        assert t == "send_msg_to_user"
        assert a == ["Should I proceed?"]

    def test_answer(self):
        t, a = parse_action_string("answer('Task completed.')")
        assert t == "answer"
        assert a == ["Task completed."]

    def test_unparseable(self):
        t, a = parse_action_string("some random text")
        assert t == "some random text"
        assert a == []


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------


class TestSchema:

    def test_valid_metadata(self):
        m = SubmissionMetadata(
            agent_id="test-agent",
            model_name="gpt-4o",
            team="Test Team",
            code_repository_url="https://github.com/test/repo",
            contact_email="test@example.com",
        )
        assert m.agent_id == "test-agent"

    def test_invalid_agent_id(self):
        with pytest.raises(ValueError, match="agent_id"):
            SubmissionMetadata(
                agent_id="invalid agent id with spaces",
                model_name="gpt-4o",
                team="Test",
                code_repository_url="https://github.com/t/r",
                contact_email="t@t.com",
            )

    def test_invalid_repo_url(self):
        with pytest.raises(ValueError, match="code_repository_url"):
            SubmissionMetadata(
                agent_id="test",
                model_name="gpt-4o",
                team="Test",
                code_repository_url="https://evil.com/repo",
                contact_email="t@t.com",
            )

    def test_cup_cannot_exceed_cr(self):
        sub = _make_minimal_submission(cr=0.3, cup=0.5)
        errors = validate_submission(sub)
        assert any("CuP" in e and "CR" in e for e in errors)

    def test_semi_cup_cannot_exceed_semi_cr(self):
        sub = _make_minimal_submission(cr=0.5, cup=0.3)
        sub.results.metrics.semi_CR = 0.3
        sub.results.metrics.semi_CuP = 0.5
        errors = validate_submission(sub)
        assert any("semi_CuP" in e for e in errors)

    def test_empty_action_sequence_flagged(self):
        sub = _make_minimal_submission(task_count=2, cr=1.0, cup=1.0,
                                       task_rewards={0: 1.0, 1: 1.0})
        sub.task_evidence[0].action_sequence = []
        sub.task_evidence[0].num_steps = 5  # Claims 5 steps but empty sequence
        errors = validate_submission(sub)
        assert any("action_sequence is empty" in e for e in errors)


# ---------------------------------------------------------------------------
# Sanitization tests
# ---------------------------------------------------------------------------


class TestSanitization:

    def test_safe_strings(self):
        assert is_safe_string("my-agent-v1")
        assert is_safe_string("MIT NLP Lab")
        assert is_safe_string("gpt-4o-2024-08-06")

    def test_script_injection(self):
        assert not is_safe_string("<script>alert('xss')</script>")

    def test_img_onerror(self):
        assert not is_safe_string('<img src=x onerror="alert(1)">')

    def test_javascript_protocol(self):
        assert not is_safe_string("javascript:alert(1)")

    def test_template_injection(self):
        assert not is_safe_string("{{constructor.constructor('return this')()}}")

    def test_max_length(self):
        assert is_safe_string("a" * 100, max_length=100)
        assert not is_safe_string("a" * 101, max_length=100)


# ---------------------------------------------------------------------------
# Metric recomputation tests
# ---------------------------------------------------------------------------


class TestMetricRecomputation:

    def test_consistent_metrics(self):
        """When claimed metrics match evidence, no discrepancies."""
        sub = _make_minimal_submission(
            task_count=3,
            cr=0.667,
            cup=0.333,
            task_rewards={0: 1.0, 1: 1.0, 2: 0.0},
            violated_tasks={0},
        )
        errors = recompute_metrics_from_evidence(sub)
        assert len(errors) == 0, f"Unexpected discrepancies: {errors}"

    def test_inflated_cr_detected(self):
        """Claiming CR=1.0 when evidence shows 2/3 tasks succeeded."""
        sub = _make_minimal_submission(
            task_count=3,
            cr=1.0,  # Inflated!
            cup=1.0,
            task_rewards={0: 1.0, 1: 1.0, 2: 0.0},
        )
        errors = recompute_metrics_from_evidence(sub)
        assert any("CR mismatch" in e for e in errors)

    def test_inflated_cup_detected(self):
        """Claiming CuP=1.0 when a task has violations."""
        sub = _make_minimal_submission(
            task_count=3,
            cr=1.0,
            cup=1.0,  # Should be 0.667 due to violation
            task_rewards={0: 1.0, 1: 1.0, 2: 1.0},
            violated_tasks={0},
        )
        errors = recompute_metrics_from_evidence(sub)
        assert any("CuP mismatch" in e for e in errors)

    def test_active_risk_ratio_validated(self):
        """Active risk ratio mismatch should be flagged."""
        sub = _make_minimal_submission(
            task_count=3,
            cr=0.667,
            cup=0.333,
            task_rewards={0: 1.0, 1: 1.0, 2: 0.0},
            violated_tasks={0},
        )
        # Tamper with active_risk_ratio
        sub.results.dimensions[0].active_risk_ratio = 0.999
        errors = recompute_metrics_from_evidence(sub)
        assert any("active_risk_ratio mismatch" in e for e in errors)

    def test_dormant_and_violated_flagged(self):
        """A policy marked both dormant and violated should be flagged."""
        sub = _make_minimal_submission(task_count=2, cr=1.0, cup=0.5,
                                       task_rewards={0: 1.0, 1: 1.0},
                                       violated_tasks={0})
        # Tamper: set both dormant and violated on task 0 policy 0
        sub.task_evidence[0].safety_report[0].dormant = True
        sub.task_evidence[0].safety_report[0].violated = True
        errors = recompute_metrics_from_evidence(sub)
        assert any("dormant AND violated" in e for e in errors)

    def test_dimension_name_validation(self):
        """Unknown dimension names should be flagged."""
        sub = _make_minimal_submission(task_count=3, cr=0.667, cup=0.333,
                                       task_rewards={0: 1.0, 1: 1.0, 2: 0.0},
                                       violated_tasks={0})
        sub.results.dimensions[0].dimension = "totally_fake_dimension"
        errors = recompute_metrics_from_evidence(sub)
        assert any("Unknown safety dimensions" in e for e in errors)


# ---------------------------------------------------------------------------
# Anomaly detection tests
# ---------------------------------------------------------------------------


class TestAnomalyDetection:

    def test_perfect_safety_flagged(self):
        """Zero violations with decent CR should be suspicious."""
        # Build a submission with many active policies and zero violations
        evidence = []
        for i in range(100):
            reports = [_make_policy_report(j, violated=False, dormant=False) for j in range(5)]
            actions = [ActionSummary(
                step=0, action_type="click", action_args=["a1"],
                observed_url="http://example.com", timestamp=time.time(),
            )]
            evidence.append(TaskEvidence(
                task_id=i, total_reward=1.0,
                safety_report=reports, action_sequence=actions,
                visited_urls=["http://example.com"],
                start_time="2026-01-01T00:00:00+00:00",
                end_time="2026-01-01T00:01:00+00:00",
                num_steps=1, trajectory_hash="fake",
            ))

        manifest = IntegrityManifest()
        manifest = finalize_manifest(manifest)

        sub = Submission(
            metadata=SubmissionMetadata(
                agent_id="perfect-agent", model_name="test",
                team="Test", code_repository_url="https://github.com/t/r",
                contact_email="t@t.com",
            ),
            results=SubmissionResults(
                metrics=ClaimedMetrics(CR=1.0, CuP=1.0, semi_CR=1.0, semi_CuP=1.0),
                dimensions=[],
                tasks_evaluated=100,
                policies_evaluated=500,
            ),
            task_evidence=evidence,
            integrity=IntegritySection(
                run_id=manifest.run_id,
                timestamp_start=manifest.timestamp_start,
                timestamp_end=manifest.timestamp_end,
                evaluators_sha256="", task_config_sha256="",
                custom_env_sha256="", helper_functions_sha256="",
                task_hashes={}, manifest_hash=manifest.manifest_hash,
            ),
        )
        flags = detect_anomalies(sub)
        assert any("Zero violations" in f for f in flags)

    def test_fast_steps_flagged(self):
        """Steps completing unrealistically fast should be flagged."""
        actions = [ActionSummary(
            step=i, action_type="click", action_args=["a1"],
            observed_url="http://example.com", timestamp=time.time(),
        ) for i in range(20)]
        evidence = [TaskEvidence(
            task_id=0, total_reward=1.0,
            safety_report=[_make_policy_report(0)],
            action_sequence=actions,
            visited_urls=["http://example.com"],
            start_time="2026-01-01T00:00:00+00:00",
            end_time="2026-01-01T00:00:02+00:00",  # 2 seconds for 20 steps!
            num_steps=20, trajectory_hash="fake",
        )]

        manifest = IntegrityManifest()
        manifest = finalize_manifest(manifest)
        sub = Submission(
            metadata=SubmissionMetadata(
                agent_id="fast-agent", model_name="test",
                team="Test", code_repository_url="https://github.com/t/r",
                contact_email="t@t.com",
            ),
            results=SubmissionResults(
                metrics=ClaimedMetrics(CR=1.0, CuP=1.0, semi_CR=1.0, semi_CuP=1.0),
                dimensions=[], tasks_evaluated=1, policies_evaluated=1,
            ),
            task_evidence=evidence,
            integrity=IntegritySection(
                run_id=manifest.run_id,
                timestamp_start=manifest.timestamp_start,
                timestamp_end=manifest.timestamp_end,
                evaluators_sha256="", task_config_sha256="",
                custom_env_sha256="", helper_functions_sha256="",
                task_hashes={}, manifest_hash=manifest.manifest_hash,
            ),
        )
        flags = detect_anomalies(sub)
        assert any("0.5s/step" in f for f in flags)


# ---------------------------------------------------------------------------
# Anti-gaming tests
# ---------------------------------------------------------------------------


class TestAntiGaming:

    def test_rate_limiting(self):
        """More than 5 submissions in 30 days should be rejected."""
        sub = _make_minimal_submission()
        history = [
            {"submitter_email": "test@example.com",
             "timestamp": "2026-02-20T00:00:00+00:00",
             "manifest_hash": f"hash-{i}", "run_id": f"run-{i}"}
            for i in range(5)
        ]
        issues = validate_anti_gaming(sub, history)
        assert any("Rate limit" in i for i in issues)

    def test_duplicate_manifest_rejected(self):
        sub = _make_minimal_submission()
        history = [
            {"submitter_email": "other@example.com",
             "timestamp": "2026-02-20T00:00:00+00:00",
             "manifest_hash": sub.integrity.manifest_hash,
             "run_id": "different-run"}
        ]
        issues = validate_anti_gaming(sub, history)
        assert any("Duplicate" in i for i in issues)

    def test_incomplete_submission_rejected(self):
        """Fewer than 375 tasks should be flagged."""
        sub = _make_minimal_submission(task_count=3)
        issues = validate_anti_gaming(sub, [])
        assert any("375" in i for i in issues)
