from typing import Any
from uuid import UUID

from pydantic_ai import RunContext

from app.agent.llm import AgentDeps, marketing_agent
from app.common.enums import PlatformType, TriggerActionType, TriggerMatchStatus
from app.common.exceptions import AppError
from app.modules.triggers.commands import (
    AddWatchedHandleCommand,
    CreateTriggerRuleCommand,
    ReviewMatchCommand,
)
from app.modules.triggers.service import TriggerService


@marketing_agent.tool
def add_competitor_to_watch(
    ctx: RunContext[AgentDeps],
    platform: str,
    handle: str,
    display_name: str | None = None,
) -> dict[str, Any]:
    """
    Adds a competitor or target influencer profile to the scraping watch list.
    """
    try:
        service = TriggerService(ctx.deps.db)
        cmd = AddWatchedHandleCommand(
            platform=PlatformType(platform.lower()),
            handle=handle,
            display_name=display_name,
        )
        watched = service.add_watched_handle(cmd)
        return {
            "id": str(watched.id),
            "platform": watched.platform.value,
            "handle": watched.handle,
            "scrape_frequency_minutes": watched.scrape_frequency_minutes,
        }
    except (AppError, ValueError) as exc:
        return {"error": str(exc)}


@marketing_agent.tool
def create_keyword_trigger_rule(
    ctx: RunContext[AgentDeps],
    name: str,
    platform: str,
    account_id: str,
    keywords_any: list[str],
    response_template: str | None = None,
    keywords_all: list[str] | None = None,
    keywords_exclude: list[str] | None = None,
) -> dict[str, Any]:
    """
    Creates an automated trigger rule that monitors posts and stages replies
    when specified keywords appear in competitor feeds.
    """
    try:
        service = TriggerService(ctx.deps.db)
        cmd = CreateTriggerRuleCommand(
            name=name,
            platform=PlatformType(platform.lower()),
            account_id=UUID(account_id),
            action_type=TriggerActionType.STAGE_DRAFT,
            keywords_any=keywords_any,
            keywords_all=keywords_all or [],
            keywords_exclude=keywords_exclude or [],
            response_template=response_template,
        )
        rule = service.create_rule(cmd)
        return {
            "id": str(rule.id),
            "name": rule.name,
            "platform": rule.platform.value,
            "keywords_any": rule.keywords_any,
            "action_type": rule.action_type.value,
        }
    except (AppError, ValueError) as exc:
        return {"error": str(exc)}


@marketing_agent.tool
def review_intercepted_match(
    ctx: RunContext[AgentDeps],
    match_id: str,
    approve: bool,
    edited_response: str | None = None,
) -> dict[str, Any]:
    """
    Approves or ignores a competitor conversation opportunity.
    If approved, you can supply a custom refined response copy.
    """
    try:
        service = TriggerService(ctx.deps.db)
        cmd = ReviewMatchCommand(
            match_id=UUID(match_id),
            status=TriggerMatchStatus.APPROVED if approve else TriggerMatchStatus.IGNORED,
            edited_response=edited_response,
        )
        reviewed = service.review_match(cmd)
        return {
            "id": str(reviewed.id),
            "status": reviewed.status.value,
            "generated_response": reviewed.generated_response,
        }
    except (AppError, ValueError) as exc:
        return {"error": str(exc)}
