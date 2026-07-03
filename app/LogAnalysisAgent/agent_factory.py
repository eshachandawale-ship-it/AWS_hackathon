"""Agent factory with per-session caching and AgentCore Memory integration."""

from __future__ import annotations

import logging
from typing import Any

from strands import Agent
from strands.models import BedrockModel

from config import BEDROCK_MODEL_ID
from memory.session import get_memory_session_manager
from prompts.system_prompt import SYSTEM_PROMPT
from tools.cloudwatch_tools import CLOUDWATCH_TOOLS

logger = logging.getLogger(__name__)

_agent_cache: dict[str, Agent] = {}


def _build_model() -> BedrockModel:
    return BedrockModel(
        model_id=BEDROCK_MODEL_ID,
        temperature=0.2,
        max_tokens=4096,
    )


def get_or_create_agent(session_id: str, actor_id: str) -> Agent:
    """Return a cached Agent bound to the session's memory context."""
    cache_key = f"{session_id}:{actor_id}"

    if cache_key in _agent_cache:
        return _agent_cache[cache_key]

    session_manager = get_memory_session_manager(session_id, actor_id)

    agent = Agent(
        model=_build_model(),
        system_prompt=SYSTEM_PROMPT,
        tools=CLOUDWATCH_TOOLS,
        session_manager=session_manager,
    )

    _agent_cache[cache_key] = agent
    logger.info(
        "Created agent for session=%s actor=%s memory=%s",
        session_id,
        actor_id,
        "enabled" if session_manager else "disabled",
    )
    return agent


def extract_context_ids(request: dict[str, Any], context: Any = None) -> tuple[str, str]:
    """Extract session and actor IDs from AgentCore context or request payload."""
    session_id = "default-session"
    actor_id = "default-analyst"

    if context is not None:
        session_id = getattr(context, "session_id", None) or session_id
        actor_id = (
            getattr(context, "user_id", None)
            or getattr(context, "actor_id", None)
            or actor_id
        )

    session_id = request.get("session_id", session_id)
    actor_id = request.get("user_id", request.get("actor_id", actor_id))

    return session_id, actor_id
