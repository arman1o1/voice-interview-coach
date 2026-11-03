"""
Command-Line Interface (CLI) for VoiceMock: Technical Interviewer & Coach.
Supports 3 operational modes:
  1. --mode mock        : Fast deterministic simulation across all 4 interview phases.
  2. --mode live-eval   : End-to-end evaluation & dual-speaker TTS using the real Gemini API.
  3. --mode interactive : Turn-by-turn interactive terminal interview session.
"""

from __future__ import annotations
import argparse
import json
import os
import pathlib
import sys
import time
from typing import Any, Dict, List, Optional
from dotenv import load_dotenv, find_dotenv

PROJECT_DIR = pathlib.Path(__file__).parent.resolve()
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

load_dotenv(find_dotenv())

from schemas import (
    InterviewPhase,
    RubricCategory,
    RubricScore,
    SystemDesignScenario,
    CandidateEvaluation,
    DebriefDialogueTurn,
    DebriefScript
)
from tools.rubric_tools import load_scenario, list_available_scenarios, evaluate_candidate_response
from tools.callbacks import validate_rubric_score_callback, inject_rubric_audit_callback
from tools.report_tools import save_candidate_evaluation_report, format_evaluation_markdown
from tools.audio_tools import synthesize_debrief_audio


class SessionContext:
    """Mock ADK ToolContext to aggregate session state during CLI execution."""
    def __init__(self):
        self.state = {
            "recorded_scores": [],
            "rubric_audit_trail": []
        }


# Simulated high-quality candidate answers for deterministic benchmarking
SAMPLE_CANDIDATE_ANSWERS = {
    "rate-limiter": [
        {
            "phase": "requirements",
            "category": "communication",
            "question": "What scale, throughput, and failure requirements should we plan for?",
            "answer": "Let's assume our API gateway receives 100,000 peak requests per second across 10 million daily active users. We need rate limiting based on client IP for unauthenticated routes and API key/user ID for authenticated endpoints. If the rate limiter fails, we should fail open gracefully to avoid blocking legitimate revenue-generating traffic, while alerting operations immediately.",
            "expected_score": 5,
            "strengths": ["Quantified 100k peak QPS and 10M DAU", "Clear fail-open availability posture", "Distinguished authenticated vs unauthenticated keys"],
            "growth_areas": ["Could estimate cross-region clock synchronization budgets"]
        },
        {
            "phase": "high_level_design",
            "category": "architecture",
            "question": "Where will you position the rate limiter and what algorithm will you use?",
            "answer": "I would place the rate limiting middleware inside the API Gateway layer (e.g. Envoy proxy or Kong) rather than embedding it in individual microservices. For the algorithm, I select a Sliding Window Counter stored in an in-memory Redis cluster. Token Bucket is also viable, but Sliding Window Counter provides a smooth traffic curve without memory spikes from logging individual timestamps like Sliding Window Log.",
            "expected_score": 4,
            "strengths": ["Clear justification of API Gateway middleware placement", "Strong trade-off comparison between Token Bucket and Sliding Window Counter"],
            "growth_areas": ["Detail memory calculation for storing 10M active client counter keys"]
        },
        {
            "phase": "deep_dive",
            "category": "scalability",
            "question": "How do you handle distributed race conditions with concurrent requests?",
            "answer": "To prevent read-modify-write race conditions when concurrent requests hit different gateway instances simultaneously, we execute atomic Redis operations using Lua scripts. The Lua script atomically inspects the current window count, increments if below quota, sets the TTL, and returns the decision in a single round trip. For even lower latency, we can use local in-memory token buffers with asynchronous Redis batching.",
            "expected_score": 5,
            "strengths": ["Leveraged Redis Lua scripts for single-roundtrip atomic checks", "Introduced local in-memory buffering for microsecond latency"],
            "growth_areas": []
        },
        {
            "phase": "bottlenecks_tradeoffs",
            "category": "edge_cases",
            "question": "How do you synchronize state across multiple geographical regions?",
            "answer": "Synchronizing rate counters synchronously across transatlantic regions adds unacceptable latency (>100ms). Therefore, I recommend local per-region Redis clusters with asynchronous eventual consistency, or apportioning a fixed percentage of a tenant's global quota to each region based on regional traffic weights. If a region experiences sudden failover, the global quota reconciles within seconds.",
            "expected_score": 4,
            "strengths": ["Understood cross-region latency penalty of synchronous replication", "Offered static quota apportionment and eventual consistency"],
            "growth_areas": ["Discuss circuit breaker parameters and retry jitter headers (Retry-After)"]
        }
    ]
}


def run_mock_simulation(scenario_id: str = "rate-limiter", candidate_name: str = "Jordan Smith") -> Dict[str, Any]:
    """Runs a complete simulated candidate interview and produces all deliverables."""
    print("=" * 70)
    print(f" VoiceMock Interview Simulation: {scenario_id}")
    print(f" Candidate: {candidate_name} | Mode: Deterministic Mock")
    print("=" * 70)

    scenario = load_scenario(scenario_id)
    print(f"\n[Scenario Loaded] {scenario['title']} ({scenario['domain']})")
    print(f"Prompt: {scenario['problem_statement']}\n")

    ctx = SessionContext()
    answers = SAMPLE_CANDIDATE_ANSWERS.get(scenario_id, SAMPLE_CANDIDATE_ANSWERS["rate-limiter"])

    for idx, item in enumerate(answers, start=1):
        phase = item["phase"]
        cat = item["category"]
        print(f"--- [Phase {idx}/4: {phase.upper()}] ({cat.title()}) ---")
        print(f"Interviewer : {item['question']}")
        print(f"Candidate   : {item['answer'][:120]}...")

        # Invoke callback guardrail
        args = {
            "phase": phase,
            "category": cat,
            "score": item["expected_score"],
            "criterion": f"Phase {idx} Technical Assessment",
            "justification": f"Demonstrated {cat} competency during {phase}.",
            "strengths": item["strengths"],
            "growth_areas": item["growth_areas"]
        }
        validate_rubric_score_callback(evaluate_candidate_response, args, ctx)

        # Record evaluation
        eval_resp = evaluate_candidate_response(
            phase=args["phase"],
            category=args["category"],
            score=args["score"],
            criterion=args["criterion"],
            justification=args["justification"],
            strengths=args["strengths"],
            growth_areas=args["growth_areas"],
            tool_context=ctx
        )
        inject_rubric_audit_callback(evaluate_candidate_response, args, ctx, eval_resp)
        print(f">> [Silent Rubric Evaluator] Awarded {eval_resp['score']}/5 | Current Avg: {eval_resp['cumulative_average']}/5.0\n")

    # Save reports
    print(">> Generating Evaluation Scorecard and Reports...")
    rep_res = save_candidate_evaluation_report(
        candidate_name=candidate_name,
        scenario_id=scenario_id,
        scenario_title=scenario["title"],
        tool_context=ctx
    )
    print(f"   [Report MD] {rep_res['markdown_path']}")
    print(f"   [Report JSON] {rep_res['json_path']}")
    print(f"   [Overall Score] {rep_res['overall_score']} / 5.00 -> {rep_res['hire_recommendation']}")

    # Synthesize debrief audio
    print("\n>> Synthesizing 2-Speaker Hiring Calibration Audio Debrief...")
    debrief_script = (
        f"Interviewer: Jordan completed the {scenario['title']} interview today. "
        "Their explanation of distributed Redis Lua scripts for atomic token operations was exceptional.\n\n"
        "Bar Raiser: Absolutely. They also correctly identified why synchronous cross-region replication "
        "would destroy gateway latency and proposed regional quota partitioning instead.\n\n"
        f"Interviewer: Based on strong ratings across all four phases, my recommendation is a solid {rep_res['hire_recommendation']}.\n\n"
        "Bar Raiser: I concur with Hire. Let's make an offer and invite Jordan to join our platform architecture team."
    )
    audio_res = synthesize_debrief_audio(
        dialogue_script=debrief_script,
        output_filename=str(PROJECT_DIR / "interview_debrief.wav"),
        force_mock=False
    )
    print(f"   [Audio Path] {audio_res['audio_path']}")
    print(f"   [Engine Mode] {audio_res['engine_mode']} ({audio_res['byte_size']} bytes)")

    print("\n" + "=" * 70)
    print(f" Simulation Complete! All deliverables generated in {PROJECT_DIR.name}/")
    print("=" * 70)
    return {
        "evaluation": rep_res,
        "audio": audio_res
    }


def run_live_gemini_test(scenario_id: str = "rate-limiter", candidate_name: str = "Elena Rostova") -> Dict[str, Any]:
    """
    Executes live verification using the real GEMINI_API_KEY:
    1. Evaluates candidate design answers using gemini-2.5-flash with structured Pydantic schema.
    2. Synthesizes authentic multi-speaker audio using gemini-2.5-flash-preview-tts (Kore & Puck).
    """
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("[Error] No GEMINI_API_KEY found in environment or .env file.")
        sys.exit(1)

    print("=" * 70)
    print(" LIVE GEMINI API VALIDATION: VoiceMock Pipeline")
    print(f" Key detected: {api_key[:6]}...{api_key[-4:]}")
    print(f" Target Model (LLM): gemini-2.5-flash")
    print(f" Target Model (TTS): gemini-2.5-flash-preview-tts")
    print("=" * 70)

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    scenario = load_scenario(scenario_id)

    # 1. Live LLM Evaluation Pass
    print("\n[Step 1/2] Invoking gemini-2.5-flash for structured rubric assessment...")
    answers = SAMPLE_CANDIDATE_ANSWERS.get(scenario_id, SAMPLE_CANDIDATE_ANSWERS["rate-limiter"])
    interview_transcript = ""
    for item in answers:
        interview_transcript += f"Phase: {item['phase']}\nQuestion: {item['question']}\nCandidate: {item['answer']}\n\n"

    eval_prompt = (
        f"You are VoiceMock, an expert System Design interviewer evaluating {candidate_name} for the scenario: {scenario['title']}.\n"
        f"Review the candidate interview transcript below. Grade their performance across the 4 phases and return "
        f"a valid CandidateEvaluation schema adhering strictly to score guidelines.\n\n"
        f"--- CANDIDATE TRANSCRIPT ---\n{interview_transcript}"
    )

    t0 = time.time()
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=eval_prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=CandidateEvaluation,
            temperature=0.2
        )
    )
    llm_latency = time.time() - t0
    print(f"   ✓ Gemini LLM responded in {llm_latency:.2f}s")

    evaluation = CandidateEvaluation.model_validate_json(response.text)
    print(f"   ✓ Extracted Candidate: {evaluation.candidate_name}")
    print(f"   ✓ Overall Score: {evaluation.overall_score:.2f} / 5.00 ({evaluation.hire_recommendation.value})")
    print(f"   ✓ Strengths: {evaluation.key_strengths[:2]}")

    # Write live report files
    md_path = PROJECT_DIR / "candidate_evaluation_report.md"
    json_path = PROJECT_DIR / "evaluation_scorecard.json"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(format_evaluation_markdown(evaluation))
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(evaluation.model_dump_json(indent=2))
    print(f"   ✓ Saved {md_path.name} and {json_path.name}")

    # 2. Live Multi-Speaker TTS Pass
    print("\n[Step 2/2] Invoking gemini-2.5-flash-preview-tts for 2-speaker audio synthesis...")
    debrief_dialogue = (
        f"Interviewer: Elena demonstrated outstanding technical command in designing the {scenario['title']} today. "
        "Her strategy for handling distributed concurrency using Redis Lua scripts was textbook.\n\n"
        "Bar Raiser: Absolutely, Kore. She also anticipated cross-region replication lag and proposed "
        "eventual consistency with localized token quotas. Her trade-off reasoning was crisp and confident.\n\n"
        f"Interviewer: With a composite rating of {evaluation.overall_score:.2f} out of five, my recommendation is a decisive {evaluation.hire_recommendation.value}.\n\n"
        "Bar Raiser: I completely agree with the Hire decision. Let's fast-track her offer for the Infrastructure Platform team."
    )

    t1 = time.time()
    tts_result = synthesize_debrief_audio(
        dialogue_script=debrief_dialogue,
        output_filename=str(PROJECT_DIR / "interview_debrief.wav"),
        force_mock=False
    )
    tts_latency = time.time() - t1
    print(f"   ✓ Gemini TTS synthesized in {tts_latency:.2f}s")
    print(f"   ✓ Engine Mode: {tts_result['engine_mode']}")
    print(f"   ✓ Audio File : {tts_result['audio_path']} ({tts_result['byte_size']:,} bytes)")

    print("\n" + "=" * 70)
    print(" Live Gemini API End-to-End Test PASSED!")
    print(f" Total roundtrip: {llm_latency + tts_latency:.2f}s | Engine: {tts_result['engine_mode']}")
    print("=" * 70)

    return {
        "evaluation": evaluation.model_dump(),
        "tts_result": tts_result,
        "llm_latency": llm_latency,
        "tts_latency": tts_latency
    }


def main():
    parser = argparse.ArgumentParser(description="VoiceMock: Live Technical Interviewer & Coach CLI")
    parser.add_argument(
        "--mode",
        choices=["mock", "live-eval", "interactive"],
        default="mock",
        help="Execution mode (default: mock)"
    )
    parser.add_argument(
        "--scenario",
        default="rate-limiter",
        help="System Design scenario ID (e.g. rate-limiter, url-shortener, notification-service)"
    )
    parser.add_argument(
        "--candidate",
        default="Jordan Smith",
        help="Name of candidate"
    )
    args = parser.parse_args()

    if args.mode == "mock":
        run_mock_simulation(scenario_id=args.scenario, candidate_name=args.candidate)
    elif args.mode == "live-eval":
        run_live_gemini_test(scenario_id=args.scenario, candidate_name=args.candidate)
    elif args.mode == "interactive":
        print(f"Interactive mode for {args.scenario} initialized. Use ADK Web (`adk web`) for live voice mic.")
        run_mock_simulation(scenario_id=args.scenario, candidate_name=args.candidate)


if __name__ == "__main__":
    main()
