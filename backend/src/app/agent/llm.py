import logging
from dataclasses import dataclass
from uuid import UUID

from pydantic_ai import Agent
from pydantic_ai.models.openrouter import OpenRouterModel
from pydantic_ai.providers.openrouter import OpenRouterProvider
from sqlalchemy.orm import Session

from app.agent.prompts import MARKETING_AGENT_SYSTEM_PROMPT
from app.core.agent_config import agent_settings
from app.core.config import settings

logger = logging.getLogger(__name__)


@dataclass
class AgentDeps:
    """Dependency container injected into every tool call."""

    db: Session
    session_id: UUID | None = None


def get_openrouter_model(model_name: str | None = None) -> OpenRouterModel:
    """
    Constructs an OpenRouterModel instance.
    Uses a safe placeholder key if OPENROUTER_API_KEY is unconfigured during unit tests.
    """
    raw_key = settings.OPENROUTER_API_KEY.get_secret_value().strip()
    api_key = raw_key if raw_key else "sk-or-v1-unconfigured-placeholder-key"

    selected_model = model_name or agent_settings.DEFAULT_MODEL
    provider = OpenRouterProvider(api_key=api_key)
    return OpenRouterModel(selected_model, provider=provider)


# The root marketing agent instance
marketing_agent: Agent[AgentDeps, str] = Agent(
    get_openrouter_model(),
    deps_type=AgentDeps,
    system_prompt=MARKETING_AGENT_SYSTEM_PROMPT,
)
