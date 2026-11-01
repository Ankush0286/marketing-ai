from typing import Any
from uuid import UUID

from pydantic_ai import RunContext

from app.agent.llm import AgentDeps, marketing_agent
from app.common.enums import (
    LeadStage,
    LeadTier,
    OutreachChannel,
    OutreachMessageStatus,
    PlatformType,
)
from app.common.exceptions import AppError
from app.modules.outreach.commands import (
    CreateLeadCommand,
    ReviewMessageCommand,
    StageMessageCommand,
)
from app.modules.outreach.service import OutreachService


@marketing_agent.tool
def add_lead_to_crm(
    ctx: RunContext[AgentDeps],
    platform: str,
    handle: str,
    display_name: str | None = None,
    bio: str | None = None,
    follower_count: int | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """
    Imports a discovered prospect or influencer lead into the social CRM.
    """
    try:
        service = OutreachService(ctx.deps.db)
        cmd = CreateLeadCommand(
            platform=PlatformType(platform.lower()),
            handle=handle,
            display_name=display_name,
            bio=bio,
            follower_count=follower_count,
            tier=LeadTier.MICRO if (follower_count or 0) > 10000 else LeadTier.NANO,
            stage=LeadStage.DISCOVERED,
            tags=tags or [],
        )
        lead = service.create_lead(cmd)
        return {
            "id": str(lead.id),
            "handle": lead.handle,
            "platform": lead.platform.value,
            "stage": lead.stage.value,
        }
    except (AppError, ValueError) as exc:
        return {"error": str(exc)}


@marketing_agent.tool
def stage_cold_outreach_dm(
    ctx: RunContext[AgentDeps],
    lead_id: str,
    account_id: str,
    message_content: str,
) -> dict[str, Any]:
    """
    Stages a personalized cold DM behind a human review gate.
    The message will not be sent until explicitly approved.
    """
    try:
        service = OutreachService(ctx.deps.db)
        cmd = StageMessageCommand(
            lead_id=UUID(lead_id),
            account_id=UUID(account_id),
            content=message_content,
            channel=OutreachChannel.DM,
        )
        msg = service.stage_message(cmd)
        return {
            "id": str(msg.id),
            "lead_id": str(msg.lead_id),
            "status": msg.status.value,
            "content_preview": msg.content[:80],
        }
    except (AppError, ValueError) as exc:
        return {"error": str(exc)}


@marketing_agent.tool
def review_staged_dm(
    ctx: RunContext[AgentDeps],
    message_id: str,
    approve: bool,
    edited_content: str | None = None,
) -> dict[str, Any]:
    """
    Human-in-the-loop review tool to approve or reject a staged cold DM.
    """
    try:
        service = OutreachService(ctx.deps.db)
        cmd = ReviewMessageCommand(
            message_id=UUID(message_id),
            status=OutreachMessageStatus.APPROVED if approve else OutreachMessageStatus.REJECTED,
            edited_content=edited_content,
        )
        reviewed = service.review_message(cmd)
        return {
            "id": str(reviewed.id),
            "status": reviewed.status.value,
            "content": reviewed.content,
        }
    except (AppError, ValueError) as exc:
        return {"error": str(exc)}
