"""
Standard Google ADK entrypoint for VoiceMock.
Exposes root_agent for the ADK Web UI (adk web).
"""

import sys
import pathlib
from dotenv import load_dotenv, find_dotenv

# Load workspace and local environment variables (.env)
load_dotenv(find_dotenv())

CURRENT_DIR = pathlib.Path(__file__).parent.resolve()
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from agents.interview_agent import root_agent

# Standard ADK convention
agent = root_agent
