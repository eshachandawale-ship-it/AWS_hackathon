"""AgentCore Memory session manager for cross-turn investigation context."""

from __future__ import annotations

import logging
import os
from typing import Optional

from bedrock_agentcore.memory.integrations.strands.config import (
    AgentCoreMemoryConfig,
    RetrievalConfig,
)
from bedrock_agentcore.memory.integrations.strands.session_manager import (
    AgentCoreMemorySessionManager,
)

from config import AWS_REGION

logger = logging.getLogger(__name__)

MEMORY_ID = os.getenv("MEMORY_LOGANALYSISMEMORY_ID")
REGION = os.getenv("AWS_REGION", AWS_REGION)


def get_memory_session_manager(
    session_id: str,
    actor_id: str,
) -> Optional[AgentCoreMemorySessionManager]:
    """Create an AgentCore Memory session manager for the given session/actor.

    Returns None when memory is not configured (local dev without deploy).
  """
    if not MEMORY_ID:
        logger.warning("MEMORY_LOGANALYSISMEMORY_ID not set — running stateless")
        return None

    if not session_id or not actor_id:
        logger.warning("Missing session_id or actor_id — skipping memory")
        return None

    retrieval_config = {
        f"/users/{actor_id}/facts": RetrievalConfig(top_k=5, relevance_score=0.4),
        f"/users/{actor_id}/preferences": RetrievalConfig(top_k=3, relevance_score=0.4),
        f"/summaries/{actor_id}": RetrievalConfig(top_k=3, relevance_score=0.4),
        f"/episodes/{actor_id}/{session_id}": RetrievalConfig(top_k=3, relevance_score=0.4),
    }

    return AgentCoreMemorySessionManager(
        AgentCoreMemoryConfig(
            memory_id=MEMORY_ID,
            session_id=session_id,
            actor_id=actor_id,
            retrieval_config=retrieval_config,
        ),
        REGION,
    )
