"""Log Analysis Agent — Amazon Bedrock AgentCore Runtime entrypoint.

Demonstrates: Runtime, Memory, Observability (auto-instrumented), Evaluations.
"""

from __future__ import annotations

import logging

from bedrock_agentcore import BedrockAgentCoreApp

from agent_factory import extract_context_ids, get_or_create_agent
from corner_cases import validate_request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = BedrockAgentCoreApp()


@app.entrypoint
async def handler(request, context=None):
    """Handle agent invocations with memory, validation, and streaming."""
    validation = validate_request(request)
    if validation:
        yield validation
        return

    prompt = request.get("prompt", request.get("input", ""))
    session_id, actor_id = extract_context_ids(request, context)

    logger.info(
        "Invocation session=%s actor=%s prompt_len=%d",
        session_id,
        actor_id,
        len(prompt),
    )

    agent = get_or_create_agent(session_id, actor_id)

    try:
        async for event in agent.stream_async(prompt):
            yield event
    except Exception as exc:
        logger.exception("Agent execution failed")
        yield {
            "error": "Agent execution failed",
            "detail": str(exc),
            "hint": "Check CloudWatch permissions and log group existence",
        }


if __name__ == "__main__":
    app.run()
