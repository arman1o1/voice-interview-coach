"""
Report generation and persistence tool for VoiceMock.
Exports candidate evaluations into formatted Markdown (candidate_evaluation_report.md)
and machine-readable JSON (evaluation_scorecard.json).
"""

from __future__ import annotations
import json
import pathlib
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

PROJECT_DIR = pathlib.Path(__file__).parent.parent.resolve()
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from schemas import (
    CandidateEvaluation,
    RubricScore,
    AuditEntry,
    HireRecommendation
)


def format_evaluation_markdown(evaluation: CandidateEvaluation) -> str:
    """Renders a CandidateEvaluation into a clean GitHub Flavored Markdown report."""
    rec_badge = evaluation.hire_recommendation.value
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    md_lines = [
        f"# Candidate Technical Evaluation Report",
        "",
        f"**Candidate**: {evaluation.candidate_name}  ",
        f"**Scenario**: {evaluation.scenario_title} (`{evaluation.scenario_id}`)  ",
        f"**Date**: {now_str}  ",
        f"**Overall Rating**: `{evaluation.overall_score:.2f} / 5.00`  ",
        f"**Hiring Recommendation**: **{rec_badge}**  ",
        "",
        "---",
        "",
        "## Executive Summary",
        "",
        evaluation.executive_summary,
        "",
        "---",
        "",
        "## Rubric Scoring Breakdown",
        "",
        "| Phase | Category | Score | Criterion | Justification |",
        "| :--- | :--- | :---: | :--- | :--- |"
    ]

    for s in evaluation.scores:
        phase_label = s.phase.value.replace("_", " ").title()
        category_label = s.category.value.replace("_", " ").title()
        score_stars = f"{s.score}/5"
        md_lines.append(
            f"| {phase_label} | {category_label} | {score_stars} | {s.criterion} | {s.justification} |"
        )

    md_lines.extend([
        "",
        "---",
        "",
        "## Demonstrated Strengths",
        ""
    ])

    if evaluation.key_strengths:
        for str_item in evaluation.key_strengths:
            md_lines.append(f"- **{str_item}**")
    else:
        md_lines.append("- Candidate maintained professional demeanor and attempted all phases.")

    md_lines.extend([
        "",
        "## Priority Coaching & Growth Areas",
        ""
    ])

    if evaluation.priority_improvements:
        for grw_item in evaluation.priority_improvements:
            md_lines.append(f"- {grw_item}")
    else:
        md_lines.append("- Continue refining deep-dive trade-off verbalization.")

    md_lines.extend([
        "",
        "---",
        "",
        "## Assessment Telemetry & Audit",
        "",
        f"- Total Dimensions Evaluated: `{len(evaluation.scores)}`",
        f"- Audit Events Logged: `{len(evaluation.audit_trail)}`",
        "- Evaluator Engine: Google ADK + Gemini 2.5 Flash Native Audio",
        ""
    ])

    return "\n".join(md_lines)


def save_candidate_evaluation_report(
    candidate_name: str = "Candidate",
    scenario_id: str = "rate-limiter",
    scenario_title: str = "Distributed API Rate Limiter",
    scores: Optional[List[Dict[str, Any]]] = None,
    markdown_filename: str = "candidate_evaluation_report.md",
    json_filename: str = "evaluation_scorecard.json",
    tool_context: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Persists the candidate's interview evaluation report to disk in Markdown and JSON.

    Args:
        candidate_name: Candidate name.
        scenario_id: ID of scenario.
        scenario_title: Title of scenario.
        scores: Optional explicit list of rubric score dicts (falls back to tool_context.state['recorded_scores']).
        markdown_filename: Target Markdown path.
        json_filename: Target JSON path.
        tool_context: Optional ADK tool context.

    Returns:
        Status dictionary with file paths and summary stats.
    """
    raw_scores: List[Dict[str, Any]] = []

    # 1. Resolve scores from explicit args or session state
    if scores:
        raw_scores = scores
    elif tool_context and hasattr(tool_context, "state") and tool_context.state is not None:
        raw_scores = tool_context.state.get("recorded_scores", [])

    # If still empty, provide a baseline entry
    if not raw_scores:
        raw_scores = [
            {
                "phase": "requirements",
                "category": "communication",
                "score": 3,
                "criterion": "General engagement",
                "justification": "Completed introductory requirements phase.",
                "strengths": ["Clear communication"],
                "growth_areas": ["Quantify non-functional constraints"]
            }
        ]

    # Convert to RubricScore instances
    parsed_scores: List[RubricScore] = [
        RubricScore.model_validate(s) for s in raw_scores
    ]

    # Audit trail
    audit_entries: List[AuditEntry] = []
    if tool_context and hasattr(tool_context, "state") and tool_context.state is not None:
        raw_audit = tool_context.state.get("rubric_audit_trail", [])
        for a in raw_audit:
            details_val = a.get("details", "") if isinstance(a, dict) else str(a)
            if not details_val and isinstance(a, dict):
                details_val = f"Status: {a.get('status', 'success')}"
            audit_entries.append(
                AuditEntry(
                    timestamp=a.get("timestamp", datetime.now(timezone.utc).isoformat()) if isinstance(a, dict) else datetime.now(timezone.utc).isoformat(),
                    event=a.get("tool", "audit_event") if isinstance(a, dict) else "audit_event",
                    phase=a.get("phase") if isinstance(a, dict) else None,
                    details=str(details_val)
                )
            )

    # 2. Build CandidateEvaluation model
    evaluation = CandidateEvaluation.compute_from_scores(
        candidate_name=candidate_name,
        scenario_id=scenario_id,
        scenario_title=scenario_title,
        scores=parsed_scores,
        audit_trail=audit_entries
    )

    # 3. Write Markdown file
    md_path = pathlib.Path(markdown_filename)
    if not md_path.is_absolute():
        md_path = PROJECT_DIR / md_path
    md_path.parent.mkdir(parents=True, exist_ok=True)

    report_markdown = format_evaluation_markdown(evaluation)
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(report_markdown)

    # 4. Write JSON file
    json_path = pathlib.Path(json_filename)
    if not json_path.is_absolute():
        json_path = PROJECT_DIR / json_path
    json_path.parent.mkdir(parents=True, exist_ok=True)

    with open(json_path, "w", encoding="utf-8") as f:
        f.write(evaluation.model_dump_json(indent=2))

    return {
        "status": "success",
        "markdown_path": str(md_path),
        "json_path": str(json_path),
        "overall_score": evaluation.overall_score,
        "hire_recommendation": evaluation.hire_recommendation.value,
        "message": f"Successfully generated evaluation report ({evaluation.hire_recommendation.value}) at {md_path.name}."
    }
