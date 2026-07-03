"""Input validation and corner-case handling for the log analysis agent."""

from __future__ import annotations

from typing import Any, Optional

MAX_PROMPT_LENGTH = 32_000
MAX_HOURS_BACK = 168  # 7 days
MIN_HOURS_BACK = 1


def validate_request(request: dict[str, Any]) -> Optional[dict[str, str]]:
    """Validate incoming request. Returns error dict or None if valid."""
    if not request:
        return {
            "error": "Empty request body",
            "hint": 'Send JSON: {"prompt": "Analyze errors in the last hour"}',
        }

    prompt = request.get("prompt", request.get("input", ""))

    if not prompt or not str(prompt).strip():
        return {
            "error": "No prompt provided",
            "hint": 'Include "prompt" field with your log analysis question',
            "example": "Analyze payment-service errors in the last 2 hours",
        }

    if len(str(prompt)) > MAX_PROMPT_LENGTH:
        return {
            "error": f"Prompt exceeds maximum length ({MAX_PROMPT_LENGTH} chars)",
            "hint": "Break the analysis into smaller questions across multiple invocations",
        }

    hours = request.get("hours_back")
    if hours is not None:
        try:
            hours_int = int(hours)
            if hours_int < MIN_HOURS_BACK or hours_int > MAX_HOURS_BACK:
                return {
                    "error": f"hours_back must be between {MIN_HOURS_BACK} and {MAX_HOURS_BACK}",
                    "hint": "Use the agent's CloudWatch tools which default to 1 hour",
                }
        except (TypeError, ValueError):
            return {"error": "hours_back must be an integer"}

    return None


def clamp_hours_back(hours_back: int) -> int:
    """Clamp hours_back to valid range."""
    return max(MIN_HOURS_BACK, min(hours_back, MAX_HOURS_BACK))


def safe_error_response(operation: str, exc: Exception) -> dict[str, str]:
    """Build a structured error response for tool failures."""
    error_code = type(exc).__name__
    if hasattr(exc, "response") and isinstance(exc.response, dict):
        error_code = exc.response.get("Error", {}).get("Code", error_code)
    message = str(exc)

    hints = {
        "AccessDeniedException": "Attach CloudWatch Logs read policy to the AgentCore runtime IAM role",
        "ResourceNotFoundException": "Log group does not exist — run scripts/seed_cloudwatch_logs.py first",
        "ThrottlingException": "CloudWatch API throttled — retry with a narrower time window",
        "MalformedQueryException": "Fix the Logs Insights query syntax",
        "InvalidParameterException": "Check log group name and filter pattern syntax",
    }

    return {
        "status": "Error",
        "operation": operation,
        "error_code": error_code,
        "message": message,
        "hint": hints.get(error_code, "Verify AWS credentials and region configuration"),
    }
