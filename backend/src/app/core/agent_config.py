import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AgentSettings:
    """Runtime configuration for LLM orchestration and Pydantic AI."""

    DEFAULT_MODEL: str = os.getenv("AGENT_MODEL", "deepseek/deepseek-v4-flash-0731")


agent_settings = AgentSettings()
