"""
Unit tests for VoiceMock tools and lifecycle callbacks.
"""

import json
import pathlib
import sys
import wave
import pytest

PROJECT_DIR = pathlib.Path(__file__).parent.parent.resolve()
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from tools.rubric_tools import (
    list_available_scenarios,
    load_scenario,
    evaluate_candidate_response
)
from tools.callbacks import (
    validate_rubric_score_callback,
    inject_rubric_audit_callback
)
from tools.report_tools import (
    format_evaluation_markdown,
    save_candidate_evaluation_report
)
from tools.audio_tools import (
    write_wave_file,
    generate_synthetic_pcm,
    normalize_debrief_script,
    synthesize_debrief_audio
)
from schemas import CandidateEvaluation, RubricScore, InterviewPhase, RubricCategory


class MockToolContext:
    def __init__(self):
        self.state = {}


def test_scenario_loader_tools():
    """Test scenario discovery and loading from JSON bank."""
    scenarios = list_available_scenarios()
    assert len(scenarios) >= 3
    ids = [s["scenario_id"] for s in scenarios]
    assert "rate-limiter" in ids
    assert "url-shortener" in ids

    scenario = load_scenario("rate-limiter")
    assert scenario["scenario_id"] == "rate-limiter"
    assert "Distributed API Rate Limiter" in scenario["title"]
    assert len(scenario["functional_requirements"]) > 0


def test_evaluate_candidate_response_with_context():
    """Test score evaluation recording and state aggregation."""
    ctx = MockToolContext()

    res1 = evaluate_candidate_response(
        phase="requirements",
        category="communication",
        score=4,
        criterion="Scale clarification",
        justification="Clarified write RPS and traffic spikes.",
        strengths=["Clear proactive inquiry"],
        growth_areas=[],
        tool_context=ctx
    )
    assert res1["status"] == "recorded"
    assert res1["score"] == 4
    assert res1["total_evaluations"] == 1
    assert res1["cumulative_average"] == 4.0

    res2 = evaluate_candidate_response(
        phase="high_level_design",
        category="architecture",
        score=5,
        criterion="Gateway component placement",
        justification="Superb API Gateway integration.",
        strengths=["Modular microservice separation"],
        growth_areas=[],
        tool_context=ctx
    )
    assert res2["total_evaluations"] == 2
    assert res2["cumulative_average"] == 4.5
    assert len(ctx.state["recorded_scores"]) == 2


def test_validate_rubric_score_callback():
    """Test before_tool_callback clamping and normalization."""
    class DummyTool:
        name = "evaluate_candidate_response"

    # Test clamping out-of-bounds score (10 -> 5)
    args = {
        "phase": "req",
        "category": "scale",
        "score": 10,
        "criterion": "  Throughput scaling  ",
        "justification": " Handled   massive traffic well.  "
    }
    result = validate_rubric_score_callback(DummyTool(), args, None)
    assert result is None  # Permits execution
    assert args["score"] == 5
    assert args["phase"] == "requirements"
    assert args["category"] == "scalability"
    assert args["criterion"] == "Throughput scaling"
    assert args["justification"] == "Handled massive traffic well."

    # Test clamping low score (-2 -> 1)
    args_low = {"score": -2}
    validate_rubric_score_callback(DummyTool(), args_low, None)
    assert args_low["score"] == 1


def test_inject_rubric_audit_callback():
    """Test after_tool_callback event telemetry logging."""
    class DummyTool:
        name = "evaluate_candidate_response"

    ctx = MockToolContext()
    args = {"phase": "deep_dive", "category": "architecture", "score": 4}
    tool_resp = {"status": "recorded", "message": "Recorded deep dive"}

    returned_resp = inject_rubric_audit_callback(DummyTool(), args, ctx, tool_resp)
    assert returned_resp == tool_resp
    assert "rubric_audit_trail" in ctx.state
    assert len(ctx.state["rubric_audit_trail"]) == 1
    entry = ctx.state["rubric_audit_trail"][0]
    assert entry["phase"] == "deep_dive"
    assert entry["score"] == 4


def test_save_candidate_evaluation_report(tmp_path):
    """Test markdown and JSON report generation."""
    md_file = tmp_path / "test_report.md"
    json_file = tmp_path / "test_scorecard.json"

    scores = [
        {
            "phase": "requirements",
            "category": "communication",
            "score": 4,
            "criterion": "Requirement probing",
            "justification": "Asked about write ratio.",
            "strengths": ["Proactive questions"],
            "growth_areas": ["Clarify edge cases"]
        },
        {
            "phase": "high_level_design",
            "category": "architecture",
            "score": 4,
            "criterion": "High level pipeline",
            "justification": "Clean diagram.",
            "strengths": ["Decoupled services"],
            "growth_areas": []
        }
    ]

    result = save_candidate_evaluation_report(
        candidate_name="Jane Developer",
        scenario_id="rate-limiter",
        scenario_title="Distributed API Rate Limiter",
        scores=scores,
        markdown_filename=str(md_file),
        json_filename=str(json_file)
    )

    assert result["status"] == "success"
    assert result["overall_score"] == 4.0
    assert md_file.exists()
    assert json_file.exists()

    md_content = md_file.read_text(encoding="utf-8")
    assert "Jane Developer" in md_content
    assert "Distributed API Rate Limiter" in md_content
    assert "| Requirements | Communication | 4/5 |" in md_content

    with open(json_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["candidate_name"] == "Jane Developer"
    assert len(data["scores"]) == 2


def test_audio_tools_wave_file_and_synthesis(tmp_path):
    """Test synthetic audio buffer and mock debrief synthesis."""
    wav_file = tmp_path / "test_debrief.wav"
    script = (
        "Interviewer: Jane showed great mastery of sliding window counters today.\n"
        "Bar Raiser: Completely agree, their design was robust and low-latency."
    )

    result = synthesize_debrief_audio(
        dialogue_script=script,
        output_filename=str(wav_file),
        force_mock=True
    )

    assert result["status"] == "success"
    assert wav_file.exists()
    assert wav_file.stat().st_size > 1000

    # Verify WAV header integrity
    with wave.open(str(wav_file), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 24000
        assert wf.getnframes() > 0
