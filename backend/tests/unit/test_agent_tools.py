from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

from sqlalchemy.orm import Session

from app.agent.llm import AgentDeps
from app.agent.tools.account_tools import (
    check_account_health,
    get_connected_accounts,
)
from app.agent.tools.campaign_tools import (
    draft_campaign,
    list_pending_posts,
    queue_social_post,
)
from app.agent.tools.outreach_tools import (
    add_lead_to_crm,
    review_staged_dm,
    stage_cold_outreach_dm,
)
from app.agent.tools.trigger_tools import (
    add_competitor_to_watch,
    create_keyword_trigger_rule,
    review_intercepted_match,
)
from app.common.enums import PlatformType
from app.modules.accounts.commands import CreateAccountCommand
from app.modules.accounts.service import AccountService


def _make_run_context(db_session: Session) -> Any:
    """Constructs a lightweight RunContext mock carrying AgentDeps."""
    ctx = MagicMock()
    ctx.deps = AgentDeps(db=db_session)
    return ctx


# =============================================================================
# Account Tools Unit Tests
# =============================================================================


def test_account_tools_execution_and_error_handling(db_session: Session):
    ctx = _make_run_context(db_session)
    acc_service = AccountService(db_session)
    account = acc_service.create_account(
        CreateAccountCommand(
            platform=PlatformType.TWITTER,
            handle="agent_growth_bot",
            daily_post_limit=12,
            daily_dm_limit=20,
        )
    )

    # 1. List connected accounts
    accounts_list = get_connected_accounts(ctx, active_only=True)
    assert len(accounts_list) == 1
    assert accounts_list[0]["handle"] == "agent_growth_bot"
    assert accounts_list[0]["can_post_today"] is True

    # 2. Check specific account health
    health = check_account_health(ctx, account_id=str(account.id))
    assert health["handle"] == "agent_growth_bot"
    assert health["remaining_posts_today"] == 12
    assert health["remaining_dms_today"] == 20

    # 3. Graceful error recovery on malformed or nonexistent UUID
    bad_uuid_res = check_account_health(ctx, account_id="not-a-valid-uuid")
    assert "error" in bad_uuid_res

    missing_res = check_account_health(ctx, account_id=str(uuid4()))
    assert "error" in missing_res


# =============================================================================
# Campaign Tools Unit Tests
# =============================================================================


def test_campaign_tools_execution_and_error_handling(db_session: Session):
    ctx = _make_run_context(db_session)
    acc_service = AccountService(db_session)
    account = acc_service.create_account(
        CreateAccountCommand(platform=PlatformType.TWITTER, handle="camp_tool_bot")
    )

    # 1. Draft a campaign
    camp_res = draft_campaign(
        ctx,
        name="AI Launch Campaign",
        description="Promoting new autonomous agent features",
        target_audience="SaaS Founders",
        tags=["ai", "saas"],
    )
    assert "id" in camp_res
    assert camp_res["name"] == "AI Launch Campaign"
    assert camp_res["status"] == "active"
    campaign_id = camp_res["id"]

    # 2. Queue a due social post
    past_due_iso = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    post_res = queue_social_post(
        ctx,
        campaign_id=campaign_id,
        account_id=str(account.id),
        content="Launching our new AI Marketing Agent today! 🚀",
        scheduled_at_iso=past_due_iso,
    )
    assert "id" in post_res
    assert post_res["status"] == "scheduled"

    # 3. List pending due posts
    pending = list_pending_posts(ctx, limit=5)
    assert len(pending) == 1
    assert pending[0]["id"] == post_res["id"]

    # 4. Graceful error recovery when queuing on nonexistent campaign
    err_res = queue_social_post(
        ctx,
        campaign_id=str(uuid4()),
        account_id=str(account.id),
        content="Should fail gracefully",
    )
    assert "error" in err_res


# =============================================================================
# Trigger Tools Unit Tests
# =============================================================================


def test_trigger_tools_execution_and_error_handling(db_session: Session):
    ctx = _make_run_context(db_session)
    acc_service = AccountService(db_session)
    account = acc_service.create_account(
        CreateAccountCommand(platform=PlatformType.TWITTER, handle="trigger_tool_bot")
    )

    # 1. Add competitor to watch
    watch_res = add_competitor_to_watch(
        ctx,
        platform="twitter",
        handle="@competitor_hq",
        display_name="Competitor HQ",
    )
    assert watch_res["handle"] == "competitor_hq"
    assert watch_res["platform"] == "twitter"

    # 2. Create keyword trigger rule
    rule_res = create_keyword_trigger_rule(
        ctx,
        name="Alternative Finder",
        platform="twitter",
        account_id=str(account.id),
        keywords_any=["expensive", "alternative"],
        response_template="Hey @{author}, check us out!",
    )
    assert "id" in rule_res
    assert rule_res["name"] == "Alternative Finder"

    # 3. Graceful error recovery on nonexistent match review
    review_err = review_intercepted_match(
        ctx,
        match_id=str(uuid4()),
        approve=True,
    )
    assert "error" in review_err


# =============================================================================
# Outreach Tools Unit Tests
# =============================================================================


def test_outreach_tools_execution_and_error_handling(db_session: Session):
    ctx = _make_run_context(db_session)
    acc_service = AccountService(db_session)
    account = acc_service.create_account(
        CreateAccountCommand(platform=PlatformType.TWITTER, handle="outreach_tool_bot")
    )

    # 1. Add lead to CRM
    lead_res = add_lead_to_crm(
        ctx,
        platform="twitter",
        handle="@tech_creator",
        display_name="Tech Creator",
        bio="Building developer tools",
        follower_count=35000,
        tags=["devtools"],
    )
    assert "id" in lead_res
    assert lead_res["handle"] == "tech_creator"
    assert lead_res["stage"] == "discovered"
    lead_id = lead_res["id"]

    # 2. Stage cold outreach DM
    stage_res = stage_cold_outreach_dm(
        ctx,
        lead_id=lead_id,
        account_id=str(account.id),
        message_content="Hey Tech Creator, love your devtool reviews!",
    )
    assert "id" in stage_res
    assert stage_res["status"] == "staged"
    message_id = stage_res["id"]

    # 3. Review and approve staged DM
    review_res = review_staged_dm(
        ctx,
        message_id=message_id,
        approve=True,
        edited_content="Hey Tech Creator, love your devtool reviews! Let's collaborate.",
    )
    assert review_res["status"] == "approved"
    assert "Let's collaborate." in review_res["content"]

    # 4. Graceful error recovery on duplicate lead import
    dup_err = add_lead_to_crm(
        ctx,
        platform="twitter",
        handle="tech_creator",
    )
    assert "error" in dup_err
