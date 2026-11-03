"""
Unit tests for VoiceMock Pydantic schemas and question bank loading.
"""

import json
import pathlib
import sys
import pytest

PROJECT_DIR = pathlib.Path(__file__).parent.parent.resolve()
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from pydantic import ValidationError
from schemas import (
    InterviewPhase,
    RubricCategory,
    HireRecommendation,
    RubricScore,
    SystemDesignScenario,
    CandidateEvaluation,
    DebriefDialogueTurn,
    DebriefScript,
    AuditEntry
)


PROJECT_DIR = pathlib.Path(__file__).parent.parent.resolve()


def test_question_bank_loads_and_validates():
    """Verify that all scenarios in interview_questions.json conform to SystemDesignScenario."""
    bank_path = PROJECT_DIR / "bank" / "interview_questions.json"
    assert bank_path.exists(), f"Missing question bank file at {bank_path}"

    with open(bank_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "scenarios" in data
    assert len(data["scenarios"]) >= 3

    for raw in data["scenarios"]:
        scenario = SystemDesignScenario.model_validate(raw)
        assert scenario.scenario_id in ["rate-limiter", "url-shortener", "notification-service"]
        assert len(scenario.functional_requirements) > 0
        assert len(scenario.suggested_questions) == 4
        assert len(scenario.rubric_guidelines) == 4


def test_rubric_score_bounds_and_enums():
    """Test valid and invalid rubric score validation."""
    score = RubricScore(
        phase=InterviewPhase.REQUIREMENTS,
        category=RubricCategory.COMMUNICATION,
        score=4,
        criterion="Scale probing",
        justification="Asked insightful clarifying questions regarding QPS and write ratio.",
        strengths=["Clear articulation"],
        growth_areas=["Could clarify SLA expectations"]
    )
    assert score.score == 4
    assert score.category == RubricCategory.COMMUNICATION

    # Test out of bounds score (< 1)
    with pytest.raises(ValidationError):
        RubricScore(
            phase=InterviewPhase.REQUIREMENTS,
            category=RubricCategory.COMMUNICATION,
            score=0,
            criterion="Too low",
            justification="Invalid score"
        )

    # Test out of bounds score (> 5)
    with pytest.raises(ValidationError):
        RubricScore(
            phase=InterviewPhase.REQUIREMENTS,
            category=RubricCategory.COMMUNICATION,
            score=6,
            criterion="Too high",
            justification="Invalid score"
        )


def test_candidate_evaluation_computation():
    """Test automatic overall score and recommendation calculation."""
    scores = [
        RubricScore(
            phase=InterviewPhase.REQUIREMENTS,
            category=RubricCategory.COMMUNICATION,
            score=5,
            criterion="Proactive requirement probing",
            justification="Excellent inquiry into scale constraints.",
            strengths=["Clarified QPS early"],
            growth_areas=[]
        ),
        RubricScore(
            phase=InterviewPhase.HIGH_LEVEL_DESIGN,
            category=RubricCategory.ARCHITECTURE,
            score=4,
            criterion="Component separation",
            justification="Solid high-level diagram with clean API Gateway decoupling.",
            strengths=["Clean gateway separation"],
            growth_areas=["Storage could be detailed further"]
        ),
        RubricScore(
            phase=InterviewPhase.DEEP_DIVE,
            category=RubricCategory.SCALABILITY,
            score=4,
            criterion="Concurrency resolution",
            justification="Good discussion of Redis Lua scripts for atomicity.",
            strengths=["Understood race conditions"],
            growth_areas=[]
        )
    ]

    evaluation = CandidateEvaluation.compute_from_scores(
        candidate_name="Alex Doe",
        scenario_id="rate-limiter",
        scenario_title="Distributed API Rate Limiter",
        scores=scores,
        audit_trail=[
            AuditEntry(
                timestamp="2026-11-03T12:00:00Z",
                event="session_started",
                phase=InterviewPhase.REQUIREMENTS.value
            )
        ]
    )

    assert evaluation.overall_score == 4.33
    assert evaluation.hire_recommendation == HireRecommendation.HIRE
    assert len(evaluation.key_strengths) >= 2
    assert len(evaluation.audit_trail) == 1


def test_debrief_script_formatting():
    """Test text serialization of debrief turns."""
    script = DebriefScript(
        scenario_title="Distributed API Rate Limiter",
        hire_recommendation="Hire",
        turns=[
            DebriefDialogueTurn(
                speaker="Interviewer",
                dialogue="Alex showed great understanding of token bucket rate limiting today."
            ),
            DebriefDialogueTurn(
                speaker="Bar Raiser",
                dialogue="Agreed! Especially their use of Redis Lua scripts to avoid race conditions."
            )
        ]
    )
    formatted = script.to_formatted_text()
    assert "Interviewer: Alex showed great" in formatted
    assert "Bar Raiser: Agreed! Especially" in formatted
