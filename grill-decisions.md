# VoiceMock Design Decisions Log

**Project**: VoiceMock — Live Interactive Technical Interviewer & Coach  
**Directory**: `Projects/voice-interview-coach/`  
**Status**: Resolved  

---

## 1. Decision Table

| # | Decision | Depends on | Status | Choice | Why |
|---|----------|-----------|--------|--------|-----|
| 1 | Core Framework & Stack | — | resolved | Google ADK + GenAI SDK + Pydantic v2 | Standard course stack across L1–L6 |
| 2 | Model Selection & TTS Engine | 1 | resolved | Gemini 2.5 Flash Native Audio + Preview TTS | Required for live streaming voice and multi-speaker synthesis |
| 3 | Core Multi-Agent Architecture | 1 | resolved | Coordinator-Dispatcher + AgentTool Specialist | Established pattern from L4/L6 for silent background processing |
| 4 | Output Artifacts & Deliverables | 1 | resolved | Markdown Report + JSON Scorecard + 24 kHz WAV Audio | Complete evaluation suite for candidate review |
| 5 | Interview Domain & Technical Focus Track | — | resolved | System Design & Architecture | Best fit for natural spoken voice dialogue and architectural trade-off discussions |
| 6 | Interaction & Runner Architecture | 5 | resolved | Hybrid: CLI runner + ADK Web voice | Enables fast reproducible CLI simulation/testing and real-time live mic practice |
| 7 | Rubric Evaluation & State Persistence Timing | 5 | resolved | Multi-stage continuous scoring in `tool_context.state` | Agent evaluates silently across interview phases (Requirements, Architecture, Deep Dive, Bottlenecks) |
| 8 | Audio Debrief Personas & Format | 2 | resolved | Dual-Speaker Panel: Lead Interviewer ('Kore') + Bar Raiser ('Puck') | Engaged multi-turn hiring calibration debate summarizing trade-offs and recommendation |
| 9 | Question & Rubric Bank Sourcing | 5 | resolved | Curated local JSON bank with extensible schemas | Deterministic, offline-capable, covers classic system design scenarios |

---

## 2. Shared Understanding

- **What's being built**: VoiceMock, an autonomous spoken technical interviewer and coaching agent for System Design and Architecture interviews.
- **Target User**: Software engineers practicing system design interviews and hiring teams calibrating interview rubrics.
- **Workflow**:
  1. The candidate starts an interview session (via ADK Web UI or interactive CLI).
  2. The coordinator agent selects or receives a scenario from a curated JSON bank (e.g., URL Shortener, Distributed Rate Limiter, Live Chat System).
  3. The agent conducts a multi-phase technical conversation: Requirements/Capacity Estimation $\rightarrow$ High-Level Design $\rightarrow$ Deep Dive / Data Flow $\rightarrow$ Bottlenecks & Failure Modes.
  4. Throughout the interview, the agent silently calls `evaluate_candidate_response` after key milestones, saving phase rubric scores into `tool_context.state['rubric_audit']`.
  5. `before_tool_callback` ensures score values are bounded within rubric definitions; `after_tool_callback` tracks cumulative telemetry.
  6. At the wrap-up, the agent generates:
     - `candidate_evaluation_report.md`: Comprehensive scorecard with rubric categories, qualitative critique, and hiring recommendation.
     - `evaluation_scorecard.json`: Structured machine-readable metrics.
     - `interview_debrief.wav`: 24 kHz dual-speaker debrief synthesized by `gemini-2.5-flash-preview-tts` featuring Lead Interviewer (`Kore`) and Bar Raiser (`Puck`).
- **Explicit Non-Goals**: Live syntax checking / sandbox execution of raw code files (handled purely through architectural discussions and verbal design).

---

## 3. Assumptions

- **Audio Specs**: 24 kHz 16-bit mono PCM WAV for dual-speaker debrief audio.
- **Voice Mapping**: Lead Interviewer $\rightarrow$ `Kore` (authoritative, encouraging); Bar Raiser $\rightarrow$ `Puck` (analytical, probing).
- **Environment**: Python 3.10+, `google-adk`, `google-genai`, `pydantic>=2.0`, standard libraries (`wave`, `pathlib`, `json`).
- **API Credentials**: Inherits `GEMINI_API_KEY` from workspace environment or `.env`.

---

## 4. Top Risks & Mitigations

| Risk | Impact | Mitigation |
| :--- | :--- | :--- |
| **Voice Interruption & Verbose Monologue** | Candidate gets overwhelmed or cut off during design explanations. | Prompt engineering with explicit turn-taking rules (keep questions concise, <=2 sentences, prompt the candidate to elaborate). |
| **Scoring Hallucination / Drift** | Evaluation tool generates arbitrary scores disconnected from rubric criteria. | Pydantic model (`RubricScore`) enforcing strict integer scale (1-5) and specific rubric category enums validated in `before_tool_callback`. |
| **TTS Timeout / Truncation** | Synthesis fails if debrief script exceeds audio generation budget. | Constrain debrief script generation to 8–10 exchanges (~250 words) to guarantee clean, fast synthesis in under 2 minutes of playback. |
