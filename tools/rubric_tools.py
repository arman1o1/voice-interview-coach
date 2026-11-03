"""
Evaluation and rubric tools for VoiceMock.
Manages scenario selection, phase guidance, and rubric scoring persistence
into ADK tool_context.state.
"""

from __future__ import annotations
import json
import pathlib
import sys
from typing import Any, Dict, List, Optional

PROJECT_DIR = pathlib.Path(__file__).parent.parent.resolve()
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from schemas import (
    InterviewPhase,
    RubricCategory,
    RubricScore,
    SystemDesignScenario,
)

BANK_PATH = PROJECT_DIR / "bank" / "interview_questions.json"


def _get_raw_bank() -> Dict[str, Any]:
    """Loads raw question bank JSON."""
    if not BANK_PATH.exists():
        raise FileNotFoundError(f"Question bank not found at {BANK_PATH}")
    with open(BANK_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def list_available_scenarios() -> List[Dict[str, str]]:
    """
    Returns a list of all available system design interview scenarios in the bank.

    Returns:
        List of dicts with 'scenario_id', 'title', and 'domain'.
    """
    bank = _get_raw_bank()
    return [
        {
            "scenario_id": s["scenario_id"],
            "title": s["title"],
            "domain": s["domain"]
        }
        for s in bank.get("scenarios", [])
    ]


def load_scenario(scenario_id: str = "rate-limiter") -> Dict[str, Any]:
    """
    Retrieves the complete definition, requirements, and rubric guidelines for a scenario.

    Args:
        scenario_id: Scenario identifier (e.g. 'rate-limiter', 'url-shortener', 'notification-service').

    Returns:
        Structured scenario dictionary matching SystemDesignScenario.
    """
    bank = _get_raw_bank()
    for s in bank.get("scenarios", []):
        if s["scenario_id"].lower() == scenario_id.lower().strip():
            scenario = SystemDesignScenario.model_validate(s)
            return scenario.model_dump()

    # Fallback to the first scenario if not matched
    first = bank["scenarios"][0]
    return SystemDesignScenario.model_validate(first).model_dump()


def evaluate_candidate_response(
    phase: str,
    category: str,
    score: int,
    criterion: str,
    justification: str,
    strengths: Optional[List[str]] = None,
    growth_areas: Optional[List[str]] = None,
    tool_context: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Silently evaluates a candidate's answer against a rubric criterion and saves the score.

    Args:
        phase: Interview phase ('requirements', 'high_level_design', 'deep_dive', 'bottlenecks_tradeoffs').
        category: Rubric category ('architecture', 'scalability', 'data_modeling', 'communication', 'edge_cases').
        score: Rating from 1 (poor) to 5 (exceptional).
        criterion: The specific architectural aspect or requirement being evaluated.
        justification: Concrete technical evidence explaining the score.
        strengths: Notable positive technical decisions demonstrated.
        growth_areas: Specific coaching feedback or missed trade-offs.
        tool_context: Optional ADK ToolContext to record into session state.

    Returns:
        Dictionary confirmation of recorded score and cumulative statistics.
    """
    # Normalize inputs
    norm_phase = InterviewPhase(phase.lower().strip())
    norm_category = RubricCategory(category.lower().strip())
    clamped_score = max(1, min(5, int(score)))

    rubric_entry = RubricScore(
        phase=norm_phase,
        category=norm_category,
        score=clamped_score,
        criterion=criterion.strip(),
        justification=justification.strip(),
        strengths=strengths or [],
        growth_areas=growth_areas or []
    )

    # Persist in ADK session state if present
    recorded_scores: List[Dict[str, Any]] = []
    if tool_context and hasattr(tool_context, "state") and tool_context.state is not None:
        state_scores = tool_context.state.setdefault("recorded_scores", [])
        state_scores.append(rubric_entry.model_dump())
        recorded_scores = state_scores
    else:
        recorded_scores = [rubric_entry.model_dump()]

    total_pts = sum(s["score"] for s in recorded_scores)
    avg_score = round(total_pts / len(recorded_scores), 2)

    return {
        "status": "recorded",
        "phase": norm_phase.value,
        "category": norm_category.value,
        "score": clamped_score,
        "criterion": criterion,
        "total_evaluations": len(recorded_scores),
        "cumulative_average": avg_score,
        "message": f"Successfully recorded {norm_category.value} score ({clamped_score}/5) for {norm_phase.value}."
    }
