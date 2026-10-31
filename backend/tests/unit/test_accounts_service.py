from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from app.common.enums import AccountStatus, PlatformType
from app.modules.accounts.commands import CreateAccountCommand, UpdateAccountCommand
from app.modules.accounts.exceptions import (
    AccountAlreadyExistsError,
    AccountInCooldownError,
    AccountNotFoundError,
    DailyPostQuotaExceededError,
)
from app.modules.accounts.service import AccountService


def test_create_account_encrypts_tokens(db_session: Session):
    service = AccountService(db_session)
    cmd = CreateAccountCommand(
        platform=PlatformType.TWITTER,
        handle="growth_ai",
        access_token="secret_plain_token",
        api_key="plain_api_key",
    )

    account = service.create_account(cmd)

    assert account.id is not None
    assert account.handle == "growth_ai"
    assert account.encrypted_access_token != "secret_plain_token"
    assert account.encrypted_api_key != "plain_api_key"

    decrypted = service.get_decrypted_tokens(account)
    assert decrypted["access_token"] == "secret_plain_token"
    assert decrypted["api_key"] == "plain_api_key"


def test_create_duplicate_account_raises_conflict(db_session: Session):
    service = AccountService(db_session)
    cmd = CreateAccountCommand(platform=PlatformType.TWITTER, handle="duplicate_handle")
    service.create_account(cmd)

    with pytest.raises(AccountAlreadyExistsError):
        service.create_account(cmd)


def test_get_by_id_or_raise_not_found(db_session: Session):
    service = AccountService(db_session)
    with pytest.raises(AccountNotFoundError):
        service.get_by_id_or_raise(uuid4())


def test_update_account_fields_and_rotate_credentials(db_session: Session):
    service = AccountService(db_session)
    created = service.create_account(
        CreateAccountCommand(
            platform=PlatformType.TWITTER,
            handle="update_me",
            access_token="old_token",
        )
    )

    updated = service.update_account(
        UpdateAccountCommand(
            account_id=created.id,
            display_name="New Display Name",
            daily_post_limit=25,
            access_token="new_rotated_token",
        )
    )

    assert updated.display_name == "New Display Name"
    assert updated.daily_post_limit == 25
    decrypted = service.get_decrypted_tokens(updated)
    assert decrypted["access_token"] == "new_rotated_token"


def test_delete_account(db_session: Session):
    service = AccountService(db_session)
    account = service.create_account(
        CreateAccountCommand(platform=PlatformType.TWITTER, handle="delete_me")
    )

    service.delete_account(account.id)
    assert service.get_by_id(account.id) is None

    # Deleting again raises not found
    with pytest.raises(AccountNotFoundError):
        service.delete_account(account.id)


def test_list_accounts_with_filter(db_session: Session):
    service = AccountService(db_session)
    acc1 = service.create_account(
        CreateAccountCommand(platform=PlatformType.TWITTER, handle="active_user")
    )
    acc2 = service.create_account(
        CreateAccountCommand(platform=PlatformType.INSTAGRAM, handle="inactive_user")
    )
    service.update_account(UpdateAccountCommand(account_id=acc2.id, is_active=False))

    all_accounts = service.list_accounts(active_only=False)
    active_accounts = service.list_accounts(active_only=True)

    assert len(all_accounts) == 2
    assert len(active_accounts) == 1
    assert active_accounts[0].id == acc1.id


def test_daily_post_quota_enforcement(db_session: Session):
    service = AccountService(db_session)
    cmd = CreateAccountCommand(
        platform=PlatformType.TWITTER,
        handle="quota_tester",
        daily_post_limit=1,
    )
    account = service.create_account(cmd)

    # 1st post succeeds
    service.record_post_activity(account.id)
    assert account.daily_posts_sent == 1

    # 2nd post exceeds limit
    with pytest.raises(DailyPostQuotaExceededError):
        service.record_post_activity(account.id)


def test_anti_ban_cooldown_blocks_posting(db_session: Session):
    service = AccountService(db_session)
    account = service.create_account(
        CreateAccountCommand(platform=PlatformType.TWITTER, handle="cooldown_user")
    )

    # Place account in cooldown until 1 hour from now
    cooldown_time = datetime.now(UTC) + timedelta(hours=1)
    service.set_cooldown(account.id, until=cooldown_time)

    assert account.status == AccountStatus.RATE_LIMITED
    assert account.is_in_cooldown()

    # Posting must raise AccountInCooldownError
    with pytest.raises(AccountInCooldownError):
        service.record_post_activity(account.id)


def test_record_dm_activity(db_session: Session):
    service = AccountService(db_session)
    account = service.create_account(
        CreateAccountCommand(platform=PlatformType.TWITTER, handle="dm_sender")
    )

    service.record_dm_activity(account.id)
    assert account.daily_dms_sent == 1
    assert account.last_action_at is not None
