from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic_ai import RunContext

from app.agent.llm import AgentDeps, marketing_agent
from app.common.enums import CampaignStatus, PostContentType, PostStatus
from app.common.exceptions import AppError
from app.modules.campaigns.commands import (
    CreateCampaignCommand,
    QueuePostCommand,
)
from app.modules.campaigns.service import CampaignService


@marketing_agent.tool
def draft_campaign(
    ctx: RunContext[AgentDeps],
    name: str,
    description: str | None = None,
    target_audience: str | None = None,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """
    Creates a new marketing campaign to group and organize scheduled posts.
    """
    try:
        service = CampaignService(ctx.deps.db)
        cmd = CreateCampaignCommand(
            name=name,
            description=description,
            target_audience=target_audience,
            status=CampaignStatus.ACTIVE,
            tags=tags or [],
        )
        campaign = service.create_campaign(cmd)
        return {
            "id": str(campaign.id),
            "name": campaign.name,
            "status": campaign.status.value,
            "tags": campaign.tags,
        }
    except (AppError, ValueError) as exc:
        return {"error": str(exc)}


@marketing_agent.tool
def queue_social_post(
    ctx: RunContext[AgentDeps],
    campaign_id: str,
    account_id: str,
    content: str,
    scheduled_at_iso: str | None = None,
    media_urls: list[str] | None = None,
) -> dict[str, Any]:
    """
    Queues a post for automated publishing on a connected social account.
    `scheduled_at_iso` must be a future ISO-8601 timestamp (e.g. 2026-11-05T14:00:00Z).
    If scheduled_at_iso is omitted, the post is saved as a draft.
    """
    try:
        service = CampaignService(ctx.deps.db)
        scheduled_dt: datetime | None = None
        post_status = PostStatus.DRAFT

        if scheduled_at_iso:
            scheduled_dt = datetime.fromisoformat(scheduled_at_iso.replace("Z", "+00:00"))
            post_status = PostStatus.SCHEDULED

        cmd = QueuePostCommand(
            campaign_id=UUID(campaign_id),
            account_id=UUID(account_id),
            content=content,
            content_type=PostContentType.IMAGE if media_urls else PostContentType.TEXT,
            media_urls=media_urls or [],
            scheduled_at=scheduled_dt,
            status=post_status,
        )
        post = service.queue_post(cmd)

        return {
            "id": str(post.id),
            "campaign_id": str(post.campaign_id),
            "account_id": str(post.account_id),
            "content_preview": post.content[:80],
            "status": post.status.value,
            "scheduled_at": post.scheduled_at.isoformat() if post.scheduled_at else None,
        }
    except (AppError, ValueError) as exc:
        return {"error": str(exc)}


@marketing_agent.tool
def list_pending_posts(
    ctx: RunContext[AgentDeps],
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    Lists scheduled posts that are due or queued for publishing.
    """
    service = CampaignService(ctx.deps.db)
    posts = service.get_due_posts(limit=limit)

    return [
        {
            "id": str(post.id),
            "campaign_id": str(post.campaign_id),
            "account_handle": post.account.handle,
            "platform": post.account.platform.value,
            "content": post.content,
            "scheduled_at": post.scheduled_at.isoformat() if post.scheduled_at else None,
            "retry_count": post.retry_count,
        }
        for post in posts
    ]
