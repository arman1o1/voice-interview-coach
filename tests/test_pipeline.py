"""
End-to-end integration tests for VoiceMock.
Verifies the complete interview simulation, state aggregation,
report writing, and audio synthesis pipeline.
"""

import os
import pathlib
import sys
import wave
import pytest

PROJECT_DIR = pathlib.Path(__file__).parent.parent.resolve()
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from cli import run_mock_simulation, run_live_gemini_test


def test_mock_simulation_pipeline(tmp_path):
    """Test full mock simulation produces all required deliverables."""
    res = run_mock_simulation(scenario_id="rate-limiter", candidate_name="Test Candidate")

    eval_info = res["evaluation"]
    audio_info = res["audio"]

    assert eval_info["status"] == "success"
    assert eval_info["overall_score"] >= 4.0
    assert "Hire" in eval_info["hire_recommendation"]

    # Verify report files exist and have content
    md_path = pathlib.Path(eval_info["markdown_path"])
    json_path = pathlib.Path(eval_info["json_path"])
    assert md_path.exists()
    assert md_path.stat().st_size > 200
    assert json_path.exists()
    assert json_path.stat().st_size > 100

    # Verify audio file
    audio_path = pathlib.Path(audio_info["audio_path"])
    assert audio_path.exists()
    assert audio_info["byte_size"] > 0

    with wave.open(str(audio_path), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getframerate() == 24000
        assert wf.getsampwidth() == 2


@pytest.mark.skipif(
    not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")),
    reason="GEMINI_API_KEY required for live test"
)
def test_live_gemini_api_pipeline():
    """Verify live Gemini API extraction and preview TTS synthesis when key is present."""
    res = run_live_gemini_test(scenario_id="rate-limiter", candidate_name="Live Test Candidate")

    assert "evaluation" in res
    assert "overall_score" in res["evaluation"]
    assert res["evaluation"]["overall_score"] >= 1.0

    tts_res = res["tts_result"]
    assert tts_res["status"] == "success"
    assert tts_res["byte_size"] > 1000

    audio_path = pathlib.Path(tts_res["audio_path"])
    assert audio_path.exists()

    with wave.open(str(audio_path), "rb") as wf:
        assert wf.getframerate() == 24000
        assert wf.getnframes() > 0
