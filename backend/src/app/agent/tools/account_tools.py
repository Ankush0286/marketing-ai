from typing import Any
from uuid import UUID

from pydantic_ai import RunContext

from app.agent.llm import AgentDeps, marketing_agent
from app.common.exceptions import AppError
from app.modules.accounts.service import AccountService


@marketing_agent.tool
def get_connected_accounts(
    ctx: RunContext[AgentDeps],
    active_only: bool = True,
) -> list[dict[str, Any]]:
    """
    Fetches all connected social media accounts (Twitter, Instagram, etc.)
    including their daily post and DM limits, current usage counts, and status.
    """
    service = AccountService(ctx.deps.db)
    accounts = service.list_accounts(active_only=active_only)

    return [
        {
            "id": str(acc.id),
            "platform": acc.platform.value,
            "handle": acc.handle,
            "display_name": acc.display_name,
            "status": acc.status.value,
            "is_active": acc.is_active,
            "daily_post_limit": acc.daily_post_limit,
            "daily_posts_sent": acc.daily_posts_sent,
            "daily_dm_limit": acc.daily_dm_limit,
            "daily_dms_sent": acc.daily_dms_sent,
            "can_post_today": acc.can_post_today(),
            "can_send_dm_today": acc.can_send_dm_today(),
            "is_in_cooldown": acc.is_in_cooldown(),
        }
        for acc in accounts
    ]


@marketing_agent.tool
def check_account_health(
    ctx: RunContext[AgentDeps],
    account_id: str,
) -> dict[str, Any]:
    """
    Checks specific anti-ban rate limits, active cooldown windows,
    and remaining daily capacity for a specific connected account UUID.
    """
    try:
        service = AccountService(ctx.deps.db)
        account = service.get_by_id_or_raise(UUID(account_id))
        return {
            "id": str(account.id),
            "handle": account.handle,
            "platform": account.platform.value,
            "status": account.status.value,
            "can_post_today": account.can_post_today(),
            "can_send_dm_today": account.can_send_dm_today(),
            "is_in_cooldown": account.is_in_cooldown(),
            "cooldown_until": account.cooldown_until.isoformat() if account.cooldown_until else None,
            "remaining_posts_today": max(0, account.daily_post_limit - account.daily_posts_sent),
            "remaining_dms_today": max(0, account.daily_dm_limit - account.daily_dms_sent),
        }
    except (AppError, ValueError) as exc:
        return {"error": str(exc)}
