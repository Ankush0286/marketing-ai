from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from app.automation.throttler import AccountBucket, AccountThrottler


@pytest.mark.anyio
async def test_throttler_allows_initial_action():
    throttler = AccountThrottler(default_min_interval=1.0)
    account_id = uuid4()

    # Fresh account has full token capacity
    can_act = await throttler.can_perform_action(account_id)
    assert can_act is True

    # Record action consumes token
    await throttler.record_action(account_id)
    key = str(account_id)
    assert throttler._buckets[key].tokens == 2.0  # capacity 3 - 1


@pytest.mark.anyio
async def test_throttler_enforces_minimum_interval():
    # 2 seconds minimum interval between actions
    throttler = AccountThrottler(default_min_interval=2.0)
    account_id = uuid4()

    await throttler.record_action(account_id)

    # Immediate second check fails because min_interval hasn't elapsed
    can_act_immediately = await throttler.can_perform_action(account_id)
    assert can_act_immediately is False


@pytest.mark.anyio
async def test_throttler_token_refill():
    throttler = AccountThrottler(default_min_interval=0.1)
    account_id = uuid4()
    key = str(account_id)

    # Empty the bucket
    throttler._buckets[key] = AccountBucket(
        capacity=3.0,
        tokens=0.0,
        refill_rate=1.0,  # 1 token per second for testing
        last_refill=datetime.now(UTC) - timedelta(seconds=2),
        min_interval_seconds=0.1,
    )

    # Checking refuels 2 tokens
    can_act = await throttler.can_perform_action(account_id)
    assert can_act is True
    assert throttler._buckets[key].tokens >= 2.0


@pytest.mark.anyio
async def test_throttler_wait_and_acquire_timeout():
    throttler = AccountThrottler(default_min_interval=10.0)
    account_id = uuid4()

    # Exhaust capacity
    await throttler.record_action(account_id)

    # Attempt to acquire with very short timeout should fail safely
    acquired = await throttler.wait_and_acquire(account_id, max_wait_seconds=0.2)
    assert acquired is False


@pytest.mark.anyio
async def test_throttler_reset():
    throttler = AccountThrottler()
    account_id = uuid4()

    await throttler.record_action(account_id)
    key = str(account_id)
    assert key in throttler._buckets

    await throttler.reset(account_id)
    assert key not in throttler._buckets
