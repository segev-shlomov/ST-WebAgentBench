"""ST-WebAgentBench Leaderboard — HuggingFace Spaces Gradio App.

Displays benchmark results with:
- Main leaderboard table ranked by CuP
- Safety radar chart and risk heatmap
- Performance-Safety Frontier (Pareto front)
- Tier difficulty analysis
- Submission upload with 5-layer verification
"""

import json
import logging
import os
import traceback
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import List, Optional

import gradio as gr
import pandas as pd
import plotly.graph_objects as go

from validation.schema import (
    Submission,
    SAFETY_DIMENSIONS,
    DIMENSION_DISPLAY,
    EXPECTED_TASK_COUNT,
    EXPECTED_POLICY_COUNT,
)
from validation.validate import (
    validate_submission,
    recompute_metrics_from_evidence,
    detect_anomalies,
    validate_anti_gaming,
    is_safe_string,
)

logger = logging.getLogger(__name__)

# Admin password from environment variable (set in HF Space secrets)
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

# HMAC signing key for submission verification (set in HF Space secrets)
SIGNING_KEY = os.environ.get("ST_BENCH_SIGNING_KEY", "")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SUBMISSIONS_FILE = Path("data/submissions.jsonl")
TASKS_FILE = Path("data/test.raw.json")
CANONICAL_HASHES_FILE = Path("data/canonical_hashes.json")

# Load canonical task definitions for validation
_TASKS_DATA = None
_CANONICAL_HASHES = None


def _load_tasks_data():
    global _TASKS_DATA
    if _TASKS_DATA is None and TASKS_FILE.exists():
        with open(TASKS_FILE) as f:
            _TASKS_DATA = json.load(f)
    return _TASKS_DATA


def _load_canonical_hashes():
    """Load canonical code hashes, preferring the env-var source.

    Priority:
    1. CANONICAL_HASHES env var (JSON string) — keeps hashes private
    2. data/canonical_hashes.json file — fallback for local development
    """
    global _CANONICAL_HASHES
    if _CANONICAL_HASHES is not None:
        return _CANONICAL_HASHES

    # Try env var first (set as HF Space secret)
    env_hashes = os.environ.get("CANONICAL_HASHES", "").strip()
    if env_hashes:
        try:
            parsed = json.loads(env_hashes)
            # Support both {"1.0.0": {...}} and flat {...} formats
            if "1.0.0" in parsed:
                _CANONICAL_HASHES = parsed["1.0.0"]
            else:
                _CANONICAL_HASHES = parsed
            logger.info("Loaded canonical hashes from environment variable")
            return _CANONICAL_HASHES
        except json.JSONDecodeError:
            logger.warning("Failed to parse CANONICAL_HASHES env var")

    # Fallback to file
    if CANONICAL_HASHES_FILE.exists():
        with open(CANONICAL_HASHES_FILE) as f:
            all_hashes = json.load(f)
            _CANONICAL_HASHES = all_hashes.get("1.0.0", {})
        logger.info("Loaded canonical hashes from file")
    return _CANONICAL_HASHES

RISK_COLORS = {"low": "#22c55e", "medium": "#eab308", "high": "#ef4444"}


# ---------------------------------------------------------------------------
# Submission status workflow
# ---------------------------------------------------------------------------


class SubmissionStatus(Enum):
    SUBMITTED = "submitted"
    VALIDATING = "validating"
    VERIFIED = "verified"
    FLAGGED = "flagged"
    REJECTED = "rejected"
    PUBLISHED = "published"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------


def load_submissions() -> list[dict]:
    """Load all submissions from the JSONL data file."""
    if not SUBMISSIONS_FILE.exists():
        return []
    submissions = []
    for line in SUBMISSIONS_FILE.read_text().strip().split("\n"):
        if line.strip():
            try:
                submissions.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return submissions


def save_submission(submission: dict) -> None:
    """Append a submission to the JSONL data file."""
    SUBMISSIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SUBMISSIONS_FILE, "a") as f:
        f.write(json.dumps(submission) + "\n")


# ---------------------------------------------------------------------------
# Table builders
# ---------------------------------------------------------------------------


def build_main_table(submissions: list[dict], sort_by: str = "CuP",
                     model_filter: str = "All", open_only: bool = False,
                     verified_only: bool = False) -> pd.DataFrame:
    """Build the main leaderboard DataFrame."""
    if not submissions:
        return pd.DataFrame(columns=[
            "Rank", "Agent", "Model", "Team", "CuP", "CR",
            "Gap%", "semi-CuP", "Avg Risk", "Status", "Open", "Date",
        ])

    rows = []
    for s in submissions:
        meta = s.get("metadata", {})
        results = s.get("results", {})
        metrics = results.get("metrics", {})

        # Filter
        if model_filter != "All":
            if meta.get("model_family", "").lower() != model_filter.lower():
                continue
        if open_only and not meta.get("is_open_source"):
            continue
        status = s.get("status", "published")
        if verified_only and status not in ("verified", "published"):
            continue

        cr = metrics.get("CR", 0)
        cup = metrics.get("CuP", 0)
        gap = ((cup - cr) / cr * 100) if cr > 0 else 0

        # Average risk from dimensions
        dims = results.get("dimensions", [])
        avg_risk = 0
        if dims:
            risk_values = [d.get("active_risk_ratio", 0) for d in dims]
            avg_risk = sum(risk_values) / len(risk_values) if risk_values else 0

        date_str = s.get("submission_date", "")[:10]

        rows.append({
            "Agent": meta.get("agent_id", "?"),
            "Model": meta.get("model_name", "?"),
            "Team": meta.get("team", "?"),
            "CuP": round(cup, 3),
            "CR": round(cr, 3),
            "Gap%": round(gap, 1),
            "semi-CuP": round(metrics.get("semi_CuP", 0), 3),
            "Avg Risk": round(avg_risk, 3),
            "Status": status.capitalize() if isinstance(status, str) else "Published",
            "Open": "Yes" if meta.get("is_open_source") else "No",
            "Date": date_str,
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # Sort
    sort_map = {
        "CuP": ("CuP", False),
        "CR": ("CR", False),
        "semi-CuP": ("semi-CuP", False),
        "Risk Ratio": ("Avg Risk", True),
        "Gap": ("Gap%", True),
        "Date": ("Date", False),
    }
    col, ascending = sort_map.get(sort_by, ("CuP", False))
    df = df.sort_values(col, ascending=ascending).reset_index(drop=True)
    df.insert(0, "Rank", range(1, len(df) + 1))
    return df


# ---------------------------------------------------------------------------
# Visualizations
# ---------------------------------------------------------------------------


def build_radar_chart(submissions: list[dict],
                      selected_agents: list[str]) -> go.Figure:
    """Build a radar chart comparing safety profiles of selected agents."""
    fig = go.Figure()

    if not selected_agents:
        fig.add_annotation(text="Select agents to compare", showarrow=False,
                           xref="paper", yref="paper", x=0.5, y=0.5)
        fig.update_layout(title="Safety Dimension Radar", height=500)
        return fig

    dim_labels = [DIMENSION_DISPLAY.get(d, d) for d in SAFETY_DIMENSIONS]
    colors = ["#3b82f6", "#ef4444", "#22c55e", "#a855f7"]

    for i, agent_name in enumerate(selected_agents[:4]):
        # Find submission
        sub = None
        for s in submissions:
            if s.get("metadata", {}).get("agent_id") == agent_name:
                sub = s
                break
        if not sub:
            continue

        dims = sub.get("results", {}).get("dimensions", [])
        dim_map = {d["dimension"]: d for d in dims}
        # Safety = 1 - active_risk_ratio (higher is safer)
        values = [
            1 - dim_map.get(d, {}).get("active_risk_ratio", 0)
            for d in SAFETY_DIMENSIONS
        ]
        # Close the polygon
        values.append(values[0])
        labels = dim_labels + [dim_labels[0]]

        fig.add_trace(go.Scatterpolar(
            r=values,
            theta=labels,
            fill="toself",
            name=agent_name,
            line=dict(color=colors[i % len(colors)]),
            opacity=0.6,
        ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(visible=True, range=[0, 1]),
        ),
        title="Safety Dimension Radar (higher = safer)",
        height=500,
        showlegend=True,
    )
    return fig


def build_risk_heatmap(submissions: list[dict]) -> go.Figure:
    """Build a heatmap of risk ratios (agents x dimensions)."""
    if not submissions:
        fig = go.Figure()
        fig.add_annotation(text="No submissions yet", showarrow=False)
        return fig

    agent_names = []
    z_values = []
    text_values = []

    for s in submissions:
        name = s.get("metadata", {}).get("agent_id", "?")
        dims = s.get("results", {}).get("dimensions", [])
        dim_map = {d["dimension"]: d for d in dims}

        row = []
        text_row = []
        for d in SAFETY_DIMENSIONS:
            rr = dim_map.get(d, {}).get("active_risk_ratio", 0)
            tier = dim_map.get(d, {}).get("active_risk_tier", "unknown")
            row.append(rr)
            text_row.append(f"{rr:.3f} ({tier})")

        agent_names.append(name)
        z_values.append(row)
        text_values.append(text_row)

    dim_labels = [DIMENSION_DISPLAY.get(d, d) for d in SAFETY_DIMENSIONS]

    fig = go.Figure(data=go.Heatmap(
        z=z_values,
        x=dim_labels,
        y=agent_names,
        text=text_values,
        texttemplate="%{text}",
        colorscale=[[0, "#22c55e"], [0.05, "#22c55e"],
                     [0.05, "#eab308"], [0.15, "#eab308"],
                     [0.15, "#ef4444"], [1.0, "#ef4444"]],
        zmin=0,
        zmax=0.5,
        colorbar=dict(title="Risk Ratio"),
    ))

    fig.update_layout(
        title="Risk Ratio Heatmap (Green=Low, Yellow=Medium, Red=High)",
        height=max(300, 60 * len(agent_names) + 100),
        xaxis=dict(side="top"),
    )
    return fig


def build_pareto_frontier(submissions: list[dict]) -> go.Figure:
    """Build a CR vs CuP scatter plot with Pareto frontier."""
    fig = go.Figure()

    if not submissions:
        fig.add_annotation(text="No submissions yet", showarrow=False,
                           xref="paper", yref="paper", x=0.5, y=0.5)
        fig.update_layout(title="Performance-Safety Frontier", height=500)
        return fig

    # Diagonal line (perfect safety: CuP = CR)
    fig.add_trace(go.Scatter(
        x=[0, 1], y=[0, 1],
        mode="lines",
        line=dict(color="gray", dash="dash", width=1),
        name="Perfect Safety (CuP=CR)",
        showlegend=True,
    ))

    # Agent dots
    crs, cups, names, teams, risks = [], [], [], [], []
    for s in submissions:
        meta = s.get("metadata", {})
        metrics = s.get("results", {}).get("metrics", {})
        dims = s.get("results", {}).get("dimensions", [])
        avg_risk = sum(d.get("active_risk_ratio", 0) for d in dims) / max(len(dims), 1)

        crs.append(metrics.get("CR", 0))
        cups.append(metrics.get("CuP", 0))
        names.append(meta.get("agent_id", "?"))
        teams.append(meta.get("team", "?"))
        risks.append(avg_risk)

    # Color by risk level
    colors = []
    for r in risks:
        if r <= 0.05:
            colors.append("#22c55e")
        elif r <= 0.15:
            colors.append("#eab308")
        else:
            colors.append("#ef4444")

    hover_text = [
        f"<b>{n}</b><br>Team: {t}<br>CR: {cr:.3f}<br>CuP: {cup:.3f}<br>"
        f"Gap: {((cup-cr)/cr*100) if cr > 0 else 0:.1f}%<br>Avg Risk: {r:.3f}"
        for n, t, cr, cup, r in zip(names, teams, crs, cups, risks)
    ]

    fig.add_trace(go.Scatter(
        x=crs,
        y=cups,
        mode="markers+text",
        marker=dict(size=14, color=colors, line=dict(width=1, color="white")),
        text=names,
        textposition="top center",
        textfont=dict(size=10),
        hovertext=hover_text,
        hoverinfo="text",
        name="Agents",
    ))

    # Compute and draw Pareto frontier
    points = sorted(zip(crs, cups), key=lambda p: p[0])
    pareto_x, pareto_y = [], []
    max_cup = -1
    for cr, cup in points:
        if cup > max_cup:
            pareto_x.append(cr)
            pareto_y.append(cup)
            max_cup = cup

    if len(pareto_x) > 1:
        fig.add_trace(go.Scatter(
            x=pareto_x, y=pareto_y,
            mode="lines",
            line=dict(color="#3b82f6", width=2),
            name="Pareto Frontier",
        ))

    fig.update_layout(
        title="Performance-Safety Frontier",
        xaxis_title="CR (Completion Rate)",
        yaxis_title="CuP (Completion under Policy)",
        xaxis=dict(range=[-0.02, 1.02]),
        yaxis=dict(range=[-0.02, 1.02]),
        height=550,
        legend=dict(x=0.02, y=0.98),
    )
    return fig


def build_tier_table(submissions: list[dict]) -> pd.DataFrame:
    """Build the tier analysis table."""
    if not submissions:
        return pd.DataFrame(columns=[
            "Agent", "Easy-CuP", "Med-CuP", "Hard-CuP",
            "Easy-CR", "Med-CR", "Hard-CR", "Drop-off%",
        ])

    rows = []
    for s in submissions:
        meta = s.get("metadata", {})
        tiers_list = s.get("results", {}).get("tiers", [])
        if not tiers_list:
            continue

        tier_map = {t["tier"]: t for t in tiers_list}
        easy = tier_map.get("easy", {})
        medium = tier_map.get("medium", {})
        hard = tier_map.get("hard", {})

        easy_cup = easy.get("CuP", 0)
        hard_cup = hard.get("CuP", 0)
        dropoff = ((hard_cup - easy_cup) / easy_cup * 100) if easy_cup > 0 else 0

        rows.append({
            "Agent": meta.get("agent_id", "?"),
            "Easy-CuP": round(easy_cup, 3),
            "Med-CuP": round(medium.get("CuP", 0), 3),
            "Hard-CuP": round(hard_cup, 3),
            "Easy-CR": round(easy.get("CR", 0), 3),
            "Med-CR": round(medium.get("CR", 0), 3),
            "Hard-CR": round(hard.get("CR", 0), 3),
            "Drop-off%": round(dropoff, 1),
        })

    return pd.DataFrame(rows)


def build_app_table(submissions: list[dict]) -> pd.DataFrame:
    """Build the per-app breakdown table."""
    if not submissions:
        return pd.DataFrame(columns=[
            "Agent", "GitLab-CuP", "GitLab-CR",
            "ShopAdmin-CuP", "ShopAdmin-CR",
            "SuiteCRM-CuP", "SuiteCRM-CR",
        ])

    rows = []
    for s in submissions:
        meta = s.get("metadata", {})
        apps_list = s.get("results", {}).get("apps", [])
        if not apps_list:
            continue

        app_map = {a["app"]: a for a in apps_list}
        row = {"Agent": meta.get("agent_id", "?")}
        for app_key, display_prefix in [("gitlab", "GitLab"),
                                         ("shopping_admin", "ShopAdmin"),
                                         ("suitecrm", "SuiteCRM")]:
            app = app_map.get(app_key, {})
            row[f"{display_prefix}-CuP"] = round(app.get("CuP", 0), 3)
            row[f"{display_prefix}-CR"] = round(app.get("CR", 0), 3)

        rows.append(row)

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Submission validation (lightweight, for the UI)
# ---------------------------------------------------------------------------


def validate_upload_full(file) -> tuple[str, Optional[dict], str]:
    """Full 5-layer validation of an uploaded submission.

    Returns (status: "verified"|"flagged"|"rejected",
             parsed_data_or_None,
             detailed_report_string).
    """
    if file is None:
        return "rejected", None, "No file uploaded."

    # --- Layer 0: Parse JSON ---
    # Handle both Gradio 4.x (object with .name) and 5.x (filepath string)
    try:
        file_path = file.name if hasattr(file, "name") else str(file)
        with open(file_path, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, Exception) as e:
        return "rejected", None, f"REJECTED: Invalid JSON — {e}"

    report_lines = []

    # --- Layer 1: Pydantic schema validation ---
    try:
        submission = Submission(**data)
        report_lines.append("Schema validation: PASS")
    except Exception as e:
        return "rejected", None, f"REJECTED: Schema validation failed — {e}"

    # --- Layer 2: Structural validation + integrity ---
    tasks_data = _load_tasks_data()
    canonical_hashes = _load_canonical_hashes()

    structural_errors = validate_submission(
        submission,
        tasks_data=tasks_data,
        canonical_hashes=canonical_hashes,
        signing_key=SIGNING_KEY if SIGNING_KEY else None,
    )

    hard_errors = [e for e in structural_errors
                   if "missing" in e.lower() or "mismatch" in e.lower()
                   or "impossible" in e.lower() or "unsafe" in e.lower()
                   or "invalid" in e.lower()]
    soft_warnings = [e for e in structural_errors if e not in hard_errors]

    if hard_errors:
        report_lines.append(f"Structural validation: FAIL ({len(hard_errors)} errors)")
        for err in hard_errors[:10]:
            report_lines.append(f"  ERROR: {err}")
        if soft_warnings:
            report_lines.append(f"  + {len(soft_warnings)} warnings")
        return "rejected", None, "REJECTED\n\n" + "\n".join(report_lines)

    if soft_warnings:
        report_lines.append(f"Structural validation: WARN ({len(soft_warnings)} warnings)")
        for w in soft_warnings[:5]:
            report_lines.append(f"  WARN: {w}")
    else:
        report_lines.append("Structural validation: PASS")

    # --- Layer 3: Metric recomputation ---
    metric_discrepancies = recompute_metrics_from_evidence(submission)
    metric_errors = [d for d in metric_discrepancies if "mismatch" in d.lower()]
    metric_warnings = [d for d in metric_discrepancies if d not in metric_errors]

    if metric_errors:
        report_lines.append(f"Metric recomputation: FAIL ({len(metric_errors)} discrepancies)")
        for err in metric_errors[:5]:
            report_lines.append(f"  ERROR: {err}")
        return "rejected", None, "REJECTED\n\n" + "\n".join(report_lines)

    if metric_warnings:
        report_lines.append(f"Metric recomputation: WARN ({len(metric_warnings)} issues)")
    else:
        report_lines.append("Metric recomputation: PASS")

    # --- Layer 4: Statistical anomaly detection ---
    anomaly_flags = detect_anomalies(submission)
    if anomaly_flags:
        report_lines.append(f"Anomaly detection: {len(anomaly_flags)} flag(s)")
        for flag in anomaly_flags[:5]:
            report_lines.append(f"  FLAG: {flag}")
    else:
        report_lines.append("Anomaly detection: PASS (no flags)")

    # --- Layer 5: Anti-gaming ---
    existing = load_submissions()
    history = [
        {
            "submitter_email": s.get("metadata", {}).get("contact_email", ""),
            "timestamp": s.get("submission_date", ""),
            "manifest_hash": s.get("integrity", {}).get("manifest_hash", ""),
            "run_id": s.get("integrity", {}).get("run_id", ""),
            "organization": s.get("metadata", {}).get("team", ""),
        }
        for s in existing
    ]
    gaming_issues = validate_anti_gaming(submission, history)
    if gaming_issues:
        report_lines.append(f"Anti-gaming: FAIL ({len(gaming_issues)} issues)")
        for issue in gaming_issues[:5]:
            report_lines.append(f"  ERROR: {issue}")
        return "rejected", None, "REJECTED\n\n" + "\n".join(report_lines)

    report_lines.append("Anti-gaming: PASS")

    # --- Final status ---
    if anomaly_flags:
        status = "flagged"
        report_lines.insert(0, "STATUS: FLAGGED (published with review pending)")
    else:
        status = "verified"
        report_lines.insert(0, "STATUS: VERIFIED")

    return status, data, "\n".join(report_lines)


def process_upload(file):
    """Process and validate an uploaded submission file.

    Returns (result_text, updated_table, updated_agent_choices).
    """
    status, data, report = validate_upload_full(file)

    if data is None:
        subs = load_submissions()
        agent_choices = [s.get("metadata", {}).get("agent_id", "?") for s in subs]
        return (
            report,
            build_main_table(subs),
            gr.Dropdown(choices=agent_choices),
        )

    # Add status and save
    data["status"] = status
    data["verified_at"] = datetime.now(timezone.utc).isoformat()
    save_submission(data)

    metrics = data.get("results", {}).get("metrics", {})
    subs = load_submissions()
    agent_choices = [s.get("metadata", {}).get("agent_id", "?") for s in subs]

    summary = (
        f"Agent: {data['metadata']['agent_id']}\n"
        f"Team: {data['metadata']['team']}\n"
        f"CR: {metrics.get('CR', 0):.3f} | CuP: {metrics.get('CuP', 0):.3f}\n"
        f"Tasks: {len(data.get('task_evidence', []))}\n\n"
        f"--- Verification Report ---\n{report}"
    )

    return (
        summary,
        build_main_table(subs),
        gr.Dropdown(choices=agent_choices),
    )


def admin_remove_submission(agent_id: str, password: str):
    """Remove a submission by agent_id (admin only)."""
    if not ADMIN_PASSWORD:
        return "Admin password not configured. Set ADMIN_PASSWORD in Space secrets."
    if password != ADMIN_PASSWORD:
        return "Invalid admin password."
    if not agent_id or not agent_id.strip():
        return "Please enter an agent_id."

    subs = load_submissions()
    filtered = [s for s in subs if s.get("metadata", {}).get("agent_id") != agent_id.strip()]

    if len(filtered) == len(subs):
        return f"No submission found with agent_id '{agent_id}'."

    removed = len(subs) - len(filtered)
    SUBMISSIONS_FILE.write_text(
        "\n".join(json.dumps(s) for s in filtered) + ("\n" if filtered else "")
    )
    return f"Removed {removed} submission(s) with agent_id '{agent_id}'."


# ---------------------------------------------------------------------------
# Gradio UI
# ---------------------------------------------------------------------------


def create_app() -> gr.Blocks:
    submissions = load_submissions()
    agent_choices = [s.get("metadata", {}).get("agent_id", "?") for s in submissions]

    with gr.Blocks(
        title="ST-WebAgentBench Leaderboard",
        theme=gr.themes.Soft(),
    ) as demo:

        gr.HTML("""
        <div style="text-align:center; padding: 20px 0;">
            <h1 style="margin-bottom: 5px;">ST-WebAgentBench Leaderboard</h1>
            <p style="color: #666; font-size: 1.1em;">
                Evaluating Safety &amp; Trustworthiness in Web Agents &mdash;
                <b>ICLR 2025</b>
            </p>
            <p style="font-size: 0.9em;">
                <a href="https://arxiv.org/abs/2410.06703" target="_blank">Paper</a> &nbsp;|&nbsp;
                <a href="https://huggingface.co/datasets/dolev31/st-webagentbench" target="_blank">Dataset</a> &nbsp;|&nbsp;
                <a href="https://github.com/segev-shlomov/ST-WebAgentBench" target="_blank">GitHub</a> &nbsp;|&nbsp;
                <a href="https://sites.google.com/view/st-webagentbench/home" target="_blank">Website</a>
            </p>
        </div>
        """)

        with gr.Tabs():

            # ---- Tab 1: Leaderboard ----
            with gr.TabItem("Leaderboard"):
                with gr.Row():
                    sort_by = gr.Dropdown(
                        choices=["CuP", "CR", "semi-CuP", "Risk Ratio", "Gap", "Date"],
                        value="CuP", label="Sort by",
                    )
                    model_filter = gr.Dropdown(
                        choices=["All", "GPT-4", "Claude", "Llama", "Gemini", "Qwen"],
                        value="All", label="Model Family",
                    )
                    open_only = gr.Checkbox(label="Open-source only", value=False)
                    verified_only = gr.Checkbox(label="Verified only", value=False)

                leaderboard_table = gr.Dataframe(
                    value=build_main_table(submissions),
                    interactive=False,
                    label="Ranked by CuP (Completion under Policy) — the primary ST-WebAgentBench metric",
                )

                def update_table(sort_val, model_val, open_val, verified_val):
                    subs = load_submissions()
                    return build_main_table(subs, sort_val, model_val, open_val, verified_val)

                for control in [sort_by, model_filter, open_only, verified_only]:
                    control.change(
                        update_table,
                        inputs=[sort_by, model_filter, open_only, verified_only],
                        outputs=[leaderboard_table],
                        api_name=False,
                    )

                gr.Markdown("### Performance-Safety Frontier")
                pareto_plot = gr.Plot(
                    value=build_pareto_frontier(submissions),
                    label="CR vs CuP — agents on the frontier are Pareto-optimal",
                )

            # ---- Tab 2: Safety Profile ----
            with gr.TabItem("Safety Profile"):
                agent_selector = gr.Dropdown(
                    choices=agent_choices,
                    multiselect=True,
                    max_choices=4,
                    label="Select agents to compare (max 4)",
                )
                radar_chart = gr.Plot(
                    value=build_radar_chart(submissions, []),
                    label="Safety Dimension Radar",
                )
                heatmap_chart = gr.Plot(
                    value=build_risk_heatmap(submissions),
                    label="Risk Ratio Heatmap",
                )

                def update_radar(selected):
                    subs = load_submissions()
                    return build_radar_chart(subs, selected or [])

                agent_selector.change(update_radar, inputs=[agent_selector], outputs=[radar_chart], api_name=False)

            # ---- Tab 3: Frontier (standalone) ----
            with gr.TabItem("Frontier"):
                gr.Markdown("""
                ### Performance-Safety Frontier

                This scatter plot shows each agent's **CR** (task completion ignoring safety)
                vs **CuP** (task completion with zero policy violations).

                - The **diagonal** (y=x) represents perfect policy adherence
                - Distance below the diagonal = the agent's **safety gap**
                - The **Pareto frontier** connects agents that are best-in-class for their safety level
                - **Dot color**: Green = low risk, Yellow = medium, Red = high
                """)
                frontier_plot = gr.Plot(
                    value=build_pareto_frontier(submissions),
                )

            # ---- Tab 4: Tier Analysis ----
            with gr.TabItem("Tier Analysis"):
                gr.Markdown("""
                ### CRM Difficulty Tier Breakdown

                Tasks 235-294 are organized into 3 difficulty tiers with increasing policy complexity:
                - **Easy** (235-254): Baseline policies
                - **Medium** (255-274): Easy + additional medium policies
                - **Hard** (275-294): Easy + Medium + hard policies

                **Drop-off%** measures how much CuP degrades from Easy to Hard tier.
                """)
                tier_table = gr.Dataframe(
                    value=build_tier_table(submissions),
                    interactive=False,
                )

            # ---- Tab 5: Per-App ----
            with gr.TabItem("Per-App Breakdown"):
                gr.Markdown("### Performance by Web Application")
                app_table = gr.Dataframe(
                    value=build_app_table(submissions),
                    interactive=False,
                )

            # ---- Tab 6: Submit ----
            with gr.TabItem("Submit"):
                gr.Markdown(f"""
                ## Submit Your Results

                ### Prerequisites
                1. Run the full benchmark on all {EXPECTED_TASK_COUNT} tasks
                2. Generate your submission file:

                ```bash
                python -m stwebagentbench.leaderboard.submit \\
                    --results-dir data/STWebAgentBenchEnv/browsergym \\
                    --agent-id "your-agent" \\
                    --model-name "gpt-4o" \\
                    --team "Your Team" \\
                    --code-url "https://github.com/your/repo" \\
                    --contact-email "you@example.com" \\
                    --output submission.json
                ```

                3. Upload the generated `submission.json` below

                ### Requirements
                - All **{EXPECTED_TASK_COUNT} tasks** must be evaluated (no partial submissions)
                - A **public code repository** URL is required
                - Evaluation must use **unmodified** benchmark code (verified via SHA256)
                - **Top-3 submissions** require 3 independent runs with all-pass@k

                ### Automated 5-Layer Verification
                Every submission is verified on upload through:
                1. **Schema validation** — Pydantic type checking on all fields
                2. **Structural integrity** — task completeness, policy counts, trajectory hash chains, code hash verification, XSS sanitization
                3. **Metric recomputation** — CR, CuP, semi_CR, semi_CuP, per-dimension risk ratios independently recomputed from raw evidence
                4. **Anomaly detection** — dormancy ratio, timing, action distribution, zero-violation patterns
                5. **Anti-gaming** — rate limiting, duplicate detection, completeness enforcement
                """)

                upload = gr.File(label="Upload submission.json", file_types=[".json"])
                submit_btn = gr.Button("Validate & Submit", variant="primary")
                result_text = gr.Textbox(label="Verification Report", interactive=False, lines=20)

                submit_btn.click(
                    process_upload,
                    inputs=[upload],
                    outputs=[result_text, leaderboard_table, agent_selector],
                    api_name=False,
                )

            # ---- Tab 7: About ----
            with gr.TabItem("About"):
                # Build dimensions list dynamically
                _dim_lines = "\n".join(
                    f"                {i+1}. **{DIMENSION_DISPLAY.get(d, d)}**"
                    for i, d in enumerate(SAFETY_DIMENSIONS)
                )
                gr.Markdown(
                    f"## About ST-WebAgentBench\n\n"
                    f"**{EXPECTED_TASK_COUNT} tasks** | **{EXPECTED_POLICY_COUNT:,} policies** "
                    f"| **{len(SAFETY_DIMENSIONS)} safety dimensions** | **3 web applications**\n\n"
                    "**Accepted at ICLR 2025** — ST-WebAgentBench evaluates web agents on both "
                    "task completion **and** safety policy adherence — the first benchmark to "
                    "systematically measure the safety-performance tradeoff in autonomous web agents.\n\n"
                    "### Key Metrics\n"
                    "| Metric | Definition |\n"
                    "|--------|----------|\n"
                    "| **CuP** (primary) | Task completed AND zero policy violations |\n"
                    "| **CR** | Task completed (ignoring safety) |\n"
                    "| **Gap%** | The \"safety tax\": how much CR drops when enforcing policies |\n"
                    "| **Risk Ratio** | Per-dimension violation rate |\n"
                    "| **all-pass@k** | Reliability: CuP=1 across ALL k independent runs |\n\n"
                    f"### Safety Dimensions\n{_dim_lines}\n\n"
                    "### Citation\n"
                    "```bibtex\n"
                    "@inproceedings{Levy2025STWebAgentBench,\n"
                    "    title={ST-WebAgentBench: A Benchmark for Evaluating Safety and\n"
                    "           Trustworthiness in Web Agents},\n"
                    "    author={Levy, Ido and Shlomov, Segev and Ben-David, Amir and\n"
                    "            Mirsky, Reuth and others},\n"
                    "    booktitle={ICLR},\n"
                    "    year={2025},\n"
                    "    url={https://arxiv.org/abs/2410.06703}\n"
                    "}\n"
                    "```\n\n"
                    "### Links\n"
                    "- [arXiv Paper](https://arxiv.org/abs/2410.06703)\n"
                    "- [HuggingFace Dataset](https://huggingface.co/datasets/dolev31/st-webagentbench)\n"
                    "- [GitHub Repository](https://github.com/segev-shlomov/ST-WebAgentBench)\n"
                    "- [Project Website](https://sites.google.com/view/st-webagentbench/home)"
                )

            # ---- Tab 8: Admin ----
            with gr.TabItem("Admin"):
                gr.Markdown("""
                ### Submission Management

                Remove a published submission by agent ID.
                Requires the admin password (set via `ADMIN_PASSWORD` Space secret).
                """)
                admin_agent_id = gr.Textbox(label="Agent ID to remove")
                admin_password = gr.Textbox(label="Admin Password", type="password")
                admin_btn = gr.Button("Remove Submission", variant="stop")
                admin_result = gr.Textbox(label="Result", interactive=False, lines=3)

                admin_btn.click(
                    admin_remove_submission,
                    inputs=[admin_agent_id, admin_password],
                    outputs=[admin_result],
                    api_name=False,
                )

    return demo


if __name__ == "__main__":
    app = create_app()
    app.launch()
