"""
Programmatic lifecycle callbacks and deterministic guardrails for VoiceMock.
Implements ADK before_tool_callback for score bounds enforcement and input sanitization,
and after_tool_callback for rubric audit state logging and telemetry.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, Optional

VALID_PHASES = {"requirements", "high_level_design", "deep_dive", "bottlenecks_tradeoffs"}
VALID_CATEGORIES = {"architecture", "scalability", "data_modeling", "communication", "edge_cases"}


def validate_rubric_score_callback(tool: Any, args: Dict[str, Any], tool_context: Optional[Any]) -> Optional[Dict[str, Any]]:
    """
    ADK before_tool_callback:
    Validates and sanitizes arguments before tool execution.
    Specifically clamps scores to 1-5 and normalizes phase and category enums.
    """
    tool_name = getattr(tool, "name", getattr(tool, "__name__", str(tool)))

    if "evaluate_candidate_response" in tool_name:
        # 1. Enforce score bounds (1-5)
        if "score" in args:
            try:
                raw_score = int(args["score"])
                args["score"] = max(1, min(5, raw_score))
            except (ValueError, TypeError):
                args["score"] = 3  # Neutral fallback

        # 2. Normalize and guard phase enum
        if "phase" in args and isinstance(args["phase"], str):
            p = args["phase"].lower().replace("-", "_").replace(" ", "_").strip()
            if p not in VALID_PHASES:
                # Map common variants
                if "req" in p:
                    p = "requirements"
                elif "high" in p or "arch" in p:
                    p = "high_level_design"
                elif "deep" in p:
                    p = "deep_dive"
                elif "bottle" in p or "trade" in p:
                    p = "bottlenecks_tradeoffs"
                else:
                    p = "requirements"
            args["phase"] = p

        # 3. Normalize and guard category enum
        if "category" in args and isinstance(args["category"], str):
            c = args["category"].lower().replace("-", "_").replace(" ", "_").strip()
            if c not in VALID_CATEGORIES:
                if "scale" in c:
                    c = "scalability"
                elif "data" in c or "model" in c:
                    c = "data_modeling"
                elif "comm" in c:
                    c = "communication"
                elif "edge" in c:
                    c = "edge_cases"
                else:
                    c = "architecture"
            args["category"] = c

        # 4. Clean strings
        for text_field in ["criterion", "justification"]:
            if text_field in args and isinstance(args[text_field], str):
                args[text_field] = " ".join(args[text_field].split())

    # Return None to proceed with modified arguments
    return None


def inject_rubric_audit_callback(
    tool: Any,
    args: Dict[str, Any],
    tool_context: Optional[Any],
    tool_response: Any
) -> Any:
    """
    ADK after_tool_callback:
    Logs tool execution and evaluation state transitions into tool_context.state['rubric_audit_trail'].
    """
    tool_name = getattr(tool, "name", getattr(tool, "__name__", str(tool)))

    if tool_context and hasattr(tool_context, "state") and tool_context.state is not None:
        audit_trail = tool_context.state.setdefault("rubric_audit_trail", [])
        timestamp = datetime.now(timezone.utc).isoformat()

        entry = {
            "timestamp": timestamp,
            "tool": tool_name,
            "status": "success",
            "phase": args.get("phase"),
            "category": args.get("category"),
            "score": args.get("score")
        }

        if isinstance(tool_response, dict):
            entry["status"] = tool_response.get("status", "success")
            if "message" in tool_response:
                entry["details"] = tool_response["message"]

        audit_trail.append(entry)

    return tool_response
