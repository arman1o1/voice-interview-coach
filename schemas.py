"""
Typed Pydantic schemas for VoiceMock technical interview coach.
Enforces validation across interview phases, scoring rubrics, scenario banks,
candidate evaluation scorecards, and multi-speaker debrief scripts.
"""

from __future__ import annotations
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, field_validator


class InterviewPhase(str, Enum):
    """Progressive phases of a technical System Design interview."""
    REQUIREMENTS = "requirements"
    HIGH_LEVEL_DESIGN = "high_level_design"
    DEEP_DIVE = "deep_dive"
    BOTTLENECKS_TRADEOFFS = "bottlenecks_tradeoffs"


class RubricCategory(str, Enum):
    """Evaluation dimensions scored during the interview."""
    ARCHITECTURE = "architecture"
    SCALABILITY = "scalability"
    DATA_MODELING = "data_modeling"
    COMMUNICATION = "communication"
    EDGE_CASES = "edge_cases"


class HireRecommendation(str, Enum):
    """Standard hiring calibration recommendations."""
    STRONG_HIRE = "Strong Hire"
    HIRE = "Hire"
    LEANING_HIRE = "Leaning Hire"
    LEANING_NO_HIRE = "Leaning No Hire"
    NO_HIRE = "No Hire"


class RubricScore(BaseModel):
    """Evaluation score for a specific category within an interview phase."""
    phase: InterviewPhase = Field(..., description="The interview phase being scored")
    category: RubricCategory = Field(..., description="The rubric category assessed")
    score: int = Field(..., ge=1, le=5, description="Score on 1-5 integer scale (1=Poor, 5=Exceptional)")
    criterion: str = Field(..., description="The specific criteria or requirement evaluated")
    justification: str = Field(..., description="Evidence-backed reasoning for the awarded score")
    strengths: List[str] = Field(default_factory=list, description="Demonstrated strengths")
    growth_areas: List[str] = Field(default_factory=list, description="Targeted areas for coaching improvement")

    @field_validator("score")
    @classmethod
    def validate_score_range(cls, v: int) -> int:
        if v < 1 or v > 5:
            raise ValueError(f"Score must be between 1 and 5 inclusive, got {v}")
        return v


class SystemDesignScenario(BaseModel):
    """Curated system design interview problem statement and rubrics."""
    scenario_id: str = Field(..., description="Unique kebab-case identifier, e.g. 'rate-limiter'")
    title: str = Field(..., description="Human-readable title, e.g. 'Distributed API Rate Limiter'")
    domain: str = Field(..., description="Engineering domain, e.g. 'Infrastructure / Security'")
    problem_statement: str = Field(..., description="Spoken problem prompt presented to candidate")
    functional_requirements: List[str] = Field(default_factory=list)
    non_functional_requirements: List[str] = Field(default_factory=list)
    suggested_questions: Dict[str, List[str]] = Field(
        default_factory=dict,
        description="Phase-keyed suggested follow-up questions"
    )
    rubric_guidelines: Dict[str, Dict[str, str]] = Field(
        default_factory=dict,
        description="Phase-keyed category scoring criteria"
    )


class AuditEntry(BaseModel):
    """Audit log entry for tracking telemetry and lifecycle events."""
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    event: str = Field(..., description="Event name, e.g. 'score_recorded', 'tool_invoked'")
    phase: Optional[str] = Field(None, description="Current interview phase if applicable")
    details: str = Field(default="", description="Summary string of event details and telemetry")


class CandidateEvaluation(BaseModel):
    """Comprehensive post-interview evaluation report and scorecard."""
    candidate_name: str = Field(default="Candidate", description="Name of candidate")
    scenario_id: str = Field(..., description="ID of interviewed scenario")
    scenario_title: str = Field(..., description="Title of interviewed scenario")
    scores: List[RubricScore] = Field(default_factory=list, description="List of recorded rubric scores")
    overall_score: float = Field(..., ge=1.0, le=5.0, description="Weighted average overall score")
    hire_recommendation: HireRecommendation = Field(..., description="Hiring committee recommendation")
    executive_summary: str = Field(..., description="High-level narrative summary of candidate performance")
    key_strengths: List[str] = Field(default_factory=list, description="Top positive technical behaviors")
    priority_improvements: List[str] = Field(default_factory=list, description="Priority improvement targets")
    audit_trail: List[AuditEntry] = Field(default_factory=list, description="Lifecycle and tool audit logs")

    @classmethod
    def compute_from_scores(
        cls,
        candidate_name: str,
        scenario_id: str,
        scenario_title: str,
        scores: List[RubricScore],
        audit_trail: Optional[List[AuditEntry]] = None
    ) -> CandidateEvaluation:
        """Helper to instantiate an evaluation with automatically computed overall score & baseline recommendation."""
        if not scores:
            avg_score = 1.0
        else:
            avg_score = round(sum(s.score for s in scores) / len(scores), 2)

        if avg_score >= 4.5:
            rec = HireRecommendation.STRONG_HIRE
        elif avg_score >= 3.7:
            rec = HireRecommendation.HIRE
        elif avg_score >= 3.0:
            rec = HireRecommendation.LEANING_HIRE
        elif avg_score >= 2.3:
            rec = HireRecommendation.LEANING_NO_HIRE
        else:
            rec = HireRecommendation.NO_HIRE

        all_strengths: List[str] = []
        all_growth: List[str] = []
        for s in scores:
            all_strengths.extend(s.strengths)
            all_growth.extend(s.growth_areas)

        summary = (
            f"Candidate completed the {scenario_title} interview with an overall rating of {avg_score}/5.0 "
            f"({rec.value}). Demonstrated proficiency across {len(scores)} evaluated dimensions."
        )

        return cls(
            candidate_name=candidate_name,
            scenario_id=scenario_id,
            scenario_title=scenario_title,
            scores=scores,
            overall_score=avg_score,
            hire_recommendation=rec,
            executive_summary=summary,
            key_strengths=list(dict.fromkeys(all_strengths))[:4],
            priority_improvements=list(dict.fromkeys(all_growth))[:4],
            audit_trail=audit_trail or []
        )


class DebriefDialogueTurn(BaseModel):
    """A single utterance in the multi-speaker post-interview debrief podcast."""
    speaker: str = Field(..., description="Must be 'Interviewer' or 'Bar Raiser'")
    dialogue: str = Field(..., description="Spoken utterance text")


class DebriefScript(BaseModel):
    """Structured container for the dual-speaker debrief conversation."""
    scenario_title: str
    hire_recommendation: str
    turns: List[DebriefDialogueTurn] = Field(default_factory=list)

    def to_formatted_text(self) -> str:
        """Formats the turns into the standard 'Speaker: Utterance' format for Gemini TTS."""
        lines = []
        for turn in self.turns:
            lines.append(f"{turn.speaker}: {turn.dialogue.strip()}")
        return "\n\n".join(lines)
