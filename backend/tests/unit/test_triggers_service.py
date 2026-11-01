from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.common.enums import PlatformType, TriggerActionType, TriggerMatchStatus
from app.modules.accounts.commands import CreateAccountCommand
from app.modules.accounts.exceptions import AccountNotFoundError
from app.modules.accounts.models import ConnectedAccount
from app.modules.accounts.service import AccountService
from app.modules.triggers.commands import (
    AddWatchedHandleCommand,
    CreateTriggerRuleCommand,
    EvaluateIncomingPostCommand,
    ReviewMatchCommand,
    UpdateTriggerRuleCommand,
    UpdateWatchedHandleCommand,
)
from app.modules.triggers.exceptions import (
    InvalidTriggerRuleError,
    TriggerMatchNotFoundError,
    WatchedHandleAlreadyExistsError,
    WatchedHandleNotFoundError,
)
from app.modules.triggers.service import TriggerService


def _create_sample_account(db: Session, handle: str = "trigger_bot") -> ConnectedAccount:
    """Helper to create a connected account used for auto-reply rules."""
    account_service = AccountService(db)
    return account_service.create_account(
        CreateAccountCommand(
            platform=PlatformType.TWITTER,
            handle=handle,
            display_name="Trigger Bot",
        )
    )


# =============================================================================
# Watched Handle Unit Tests
# =============================================================================


def test_watched_handle_crud(db_session: Session):
    service = TriggerService(db_session)

    # 1. Add watched handle (strips leading @)
    cmd = AddWatchedHandleCommand(
        platform=PlatformType.TWITTER,
        handle="@competitor_ceo",
        display_name="Competitor CEO",
        scrape_frequency_minutes=15,
    )
    handle = service.add_watched_handle(cmd)

    assert handle.id is not None
    assert handle.handle == "competitor_ceo"
    assert handle.scrape_frequency_minutes == 15

    # 2. Update
    updated = service.update_watched_handle(
        UpdateWatchedHandleCommand(
            handle_id=handle.id,
            display_name="Updated CEO",
            scrape_frequency_minutes=60,
        )
    )
    assert updated.display_name == "Updated CEO"
    assert updated.scrape_frequency_minutes == 60

    # 3. List
    handles = service.list_watched_handles()
    assert len(handles) == 1

    # 4. Delete
    service.delete_watched_handle(handle.id)
    assert service.get_watched_handle_by_id(handle.id) is None


def test_add_duplicate_watched_handle_raises(db_session: Session):
    service = TriggerService(db_session)
    service.add_watched_handle(
        AddWatchedHandleCommand(platform=PlatformType.TWITTER, handle="same_handle")
    )

    with pytest.raises(WatchedHandleAlreadyExistsError):
        service.add_watched_handle(
            AddWatchedHandleCommand(platform=PlatformType.TWITTER, handle="@same_handle")
        )


def test_get_nonexistent_handle_raises(db_session: Session):
    service = TriggerService(db_session)
    with pytest.raises(WatchedHandleNotFoundError):
        service.get_watched_handle_by_id_or_raise(uuid4())


# =============================================================================
# Trigger Rule Unit Tests
# =============================================================================


def test_trigger_rule_crud(db_session: Session):
    service = TriggerService(db_session)
    account = _create_sample_account(db_session)

    # 1. Create rule
    cmd = CreateTriggerRuleCommand(
        name="Pricing Complaint Rule",
        platform=PlatformType.TWITTER,
        account_id=account.id,
        action_type=TriggerActionType.STAGE_DRAFT,
        keywords_any=["expensive", "pricing", "#saas"],
        keywords_exclude=["hiring"],
        response_template="Hey @{author}, try our affordable alternative!",
    )
    rule = service.create_rule(cmd)

    assert rule.id is not None
    assert rule.name == "Pricing Complaint Rule"
    assert "pricing" in rule.keywords_any

    # 2. Update rule
    updated = service.update_rule(
        UpdateTriggerRuleCommand(
            rule_id=rule.id,
            name="Updated Rule Name",
            cooldown_minutes=120,
        )
    )
    assert updated.name == "Updated Rule Name"
    assert updated.cooldown_minutes == 120

    # 3. Delete rule
    service.delete_rule(rule.id)
    assert service.get_rule_by_id(rule.id) is None


def test_create_rule_without_account_raises(db_session: Session):
    service = TriggerService(db_session)
    with pytest.raises(AccountNotFoundError):
        service.create_rule(
            CreateTriggerRuleCommand(
                name="Orphan Rule",
                platform=PlatformType.TWITTER,
                account_id=uuid4(),
                keywords_any=["test"],
            )
        )


def test_create_rule_without_keywords_raises(db_session: Session):
    service = TriggerService(db_session)
    account = _create_sample_account(db_session)

    with pytest.raises(InvalidTriggerRuleError):
        service.create_rule(
            CreateTriggerRuleCommand(
                name="Empty Keywords",
                platform=PlatformType.TWITTER,
                account_id=account.id,
                keywords_any=[],
                keywords_all=[],
            )
        )


# =============================================================================
# Keyword Evaluator Engine & Deduplication Unit Tests
# =============================================================================


def test_evaluate_text_match_engine(db_session: Session):
    service = TriggerService(db_session)
    account = _create_sample_account(db_session)

    rule = service.create_rule(
        CreateTriggerRuleCommand(
            name="Evaluation Rule",
            platform=PlatformType.TWITTER,
            account_id=account.id,
            keywords_any=["alternative", "switch"],
            keywords_all=["looking", "tool"],
            keywords_exclude=["bad", "scam"],
        )
    )

    # 1. Matches: contains all required + at least one optional
    text1 = "I am looking for a new tool as an alternative."
    is_match1, kws1 = service.evaluate_text_match(rule, text1)
    assert is_match1 is True
    assert set(kws1) == {"looking", "tool", "alternative"}

    # 2. Fails: missing one required keyword ('tool')
    text2 = "I am looking for a switch."
    is_match2, _ = service.evaluate_text_match(rule, text2)
    assert is_match2 is False

    # 3. Fails: contains negative keyword ('scam')
    text3 = "I am looking for a tool alternative but it feels like a scam."
    is_match3, _ = service.evaluate_text_match(rule, text3)
    assert is_match3 is False


def test_evaluate_text_match_hashtags_and_mentions(db_session: Session):
    """Verifies that lookaround regex accurately captures #hashtags and @mentions."""
    service = TriggerService(db_session)
    account = _create_sample_account(db_session)

    rule = service.create_rule(
        CreateTriggerRuleCommand(
            name="Hashtag Rule",
            platform=PlatformType.TWITTER,
            account_id=account.id,
            keywords_any=["#marketingai", "@competitor"],
        )
    )

    # Matches #marketingai
    match, kws = service.evaluate_text_match(rule, "Loving the new #marketingai framework!")
    assert match is True
    assert "#marketingai" in kws

    # Matches @competitor
    match2, kws2 = service.evaluate_text_match(rule, "Leaving @competitor for a better option.")
    assert match2 is True
    assert "@competitor" in kws2

    # Does not falsely match substrings
    match3, _ = service.evaluate_text_match(rule, "Using #marketingairocks framework")
    assert match3 is False


def test_evaluate_incoming_post_deduplication(db_session: Session):
    """Ensures identical tweets are never processed twice for the same rule."""
    service = TriggerService(db_session)
    account = _create_sample_account(db_session)

    service.create_rule(
        CreateTriggerRuleCommand(
            name="Live Rule",
            platform=PlatformType.TWITTER,
            account_id=account.id,
            keywords_any=["ai"],
        )
    )

    post_cmd = EvaluateIncomingPostCommand(
        platform=PlatformType.TWITTER,
        platform_post_id="tweet_9999",
        author_handle="tech_enthusiast",
        post_content="Testing the best ai solutions today.",
    )

    # 1st evaluation -> creates match
    matches1 = service.evaluate_incoming_post(post_cmd)
    assert len(matches1) == 1
    assert matches1[0].platform_post_id == "tweet_9999"

    # 2nd evaluation of same tweet -> deduplicated, 0 new matches created
    matches2 = service.evaluate_incoming_post(post_cmd)
    assert len(matches2) == 0


def test_evaluate_incoming_post_author_cooldown(db_session: Session):
    """Ensures an author who matched recently is ignored within the cooldown window."""
    service = TriggerService(db_session)
    account = _create_sample_account(db_session)

    service.create_rule(
        CreateTriggerRuleCommand(
            name="Cooldown Rule",
            platform=PlatformType.TWITTER,
            account_id=account.id,
            keywords_any=["growth"],
            cooldown_minutes=60,
        )
    )

    # 1st post from user
    post1 = EvaluateIncomingPostCommand(
        platform=PlatformType.TWITTER,
        platform_post_id="tweet_001",
        author_handle="frequent_poster",
        post_content="Need growth marketing advice.",
    )
    matches1 = service.evaluate_incoming_post(post1)
    assert len(matches1) == 1

    # 2nd different post from SAME user within 60 minutes -> skipped
    post2 = EvaluateIncomingPostCommand(
        platform=PlatformType.TWITTER,
        platform_post_id="tweet_002",
        author_handle="frequent_poster",
        post_content="Still talking about growth tools.",
    )
    matches2 = service.evaluate_incoming_post(post2)
    assert len(matches2) == 0


def test_review_match_flow(db_session: Session):
    service = TriggerService(db_session)
    account = _create_sample_account(db_session)

    service.create_rule(
        CreateTriggerRuleCommand(
            name="Review Rule",
            platform=PlatformType.TWITTER,
            account_id=account.id,
            keywords_any=["help"],
            response_template="Hello @{author}!",
        )
    )

    matches = service.evaluate_incoming_post(
        EvaluateIncomingPostCommand(
            platform=PlatformType.TWITTER,
            platform_post_id="tweet_777",
            author_handle="prospect_dan",
            post_content="I need help with social media.",
        )
    )
    assert len(matches) == 1
    match = matches[0]
    assert match.status == TriggerMatchStatus.PENDING_REVIEW
    assert match.generated_response == "Hello @prospect_dan!"

    # Approve with refined response copy
    approved = service.review_match(
        ReviewMatchCommand(
            match_id=match.id,
            status=TriggerMatchStatus.APPROVED,
            edited_response="Hello prospect_dan, check our personalized demo!",
        )
    )
    assert approved.status == TriggerMatchStatus.APPROVED
    assert approved.generated_response == "Hello prospect_dan, check our personalized demo!"
    assert approved.reviewed_at is not None


def test_get_nonexistent_match_raises(db_session: Session):
    service = TriggerService(db_session)
    with pytest.raises(TriggerMatchNotFoundError):
        service.get_match_by_id_or_raise(uuid4())
