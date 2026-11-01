from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient


def _create_account_via_api(client: TestClient, handle: str = "api_bot") -> str:
    """Helper to create an account via API and return its UUID string."""
    res = client.post(
        "/api/v1/accounts/",
        json={"platform": "twitter", "handle": handle},
    )
    assert res.status_code == 201
    return res.json()["id"]


# =============================================================================
# Campaign Endpoints Integration Tests
# =============================================================================


def test_create_and_get_campaign_detail_flow(client: TestClient):
    # 1. Create campaign
    create_res = client.post(
        "/api/v1/campaigns/",
        json={
            "name": "Q1 AI Launch",
            "description": "Cross-platform marketing campaign",
            "target_audience": "Developers & Marketers",
            "tags": ["growth", "ai"],
        },
    )
    assert create_res.status_code == 201
    campaign_id = create_res.json()["id"]

    # 2. Get campaign detail (includes empty posts list initially)
    detail_res = client.get(f"/api/v1/campaigns/{campaign_id}")
    assert detail_res.status_code == 200
    data = detail_res.json()
    assert data["name"] == "Q1 AI Launch"
    assert data["posts"] == []


def test_create_campaign_invalid_dates_returns_422(client: TestClient):
    now = datetime.now(UTC)
    payload = {
        "name": "Invalid Dates",
        "start_date": (now + timedelta(days=5)).isoformat(),
        "end_date": now.isoformat(),  # end_date before start_date
    }
    response = client.post("/api/v1/campaigns/", json=payload)
    assert response.status_code == 422
    assert response.json()["error"] == "VALIDATION_ERROR"


def test_list_and_filter_campaigns(client: TestClient):
    client.post("/api/v1/campaigns/", json={"name": "Draft 1", "status": "draft"})
    client.post("/api/v1/campaigns/", json={"name": "Active 1", "status": "active"})

    # Filter active
    res = client.get("/api/v1/campaigns/?status=active")
    assert res.status_code == 200
    campaigns = res.json()
    assert len(campaigns) == 1
    assert campaigns[0]["name"] == "Active 1"


def test_patch_and_delete_campaign(client: TestClient):
    res = client.post("/api/v1/campaigns/", json={"name": "To Modify"})
    campaign_id = res.json()["id"]

    # Patch
    patch_res = client.patch(
        f"/api/v1/campaigns/{campaign_id}",
        json={"name": "Modified Name", "status": "active"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["name"] == "Modified Name"
    assert patch_res.json()["status"] == "active"

    # Delete
    del_res = client.delete(f"/api/v1/campaigns/{campaign_id}")
    assert del_res.status_code == 204

    # Subsequent GET returns 404
    get_res = client.get(f"/api/v1/campaigns/{campaign_id}")
    assert get_res.status_code == 404


# =============================================================================
# Scheduled Post Endpoints Integration Tests
# =============================================================================


def test_queue_and_manage_post_flow(client: TestClient):
    account_id = _create_account_via_api(client, "camp_poster")
    camp_res = client.post("/api/v1/campaigns/", json={"name": "Content Hub"})
    campaign_id = camp_res.json()["id"]

    future_time = (datetime.now(UTC) + timedelta(days=1)).isoformat()

    # 1. Queue Post
    queue_res = client.post(
        f"/api/v1/campaigns/{campaign_id}/posts",
        json={
            "account_id": account_id,
            "content": "Exciting product update! Check it out.",
            "content_type": "text",
            "scheduled_at": future_time,
            "status": "scheduled",
        },
    )
    assert queue_res.status_code == 201
    post_data = queue_res.json()
    post_id = post_data["id"]
    assert post_data["status"] == "scheduled"
    assert post_data["campaign_id"] == campaign_id

    # 2. Get Post by ID
    get_res = client.get(f"/api/v1/campaigns/posts/{post_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == post_id

    # 3. List Campaign Posts
    list_res = client.get(f"/api/v1/campaigns/{campaign_id}/posts")
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1

    # 4. Patch Post
    patch_res = client.patch(
        f"/api/v1/campaigns/posts/{post_id}",
        json={"content": "Updated content with more emojis! 🚀"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["content"] == "Updated content with more emojis! 🚀"

    # 5. Cancel Post
    cancel_res = client.post(f"/api/v1/campaigns/posts/{post_id}/cancel")
    assert cancel_res.status_code == 200
    assert cancel_res.json()["status"] == "cancelled"

    # 6. Delete Post
    del_res = client.delete(f"/api/v1/campaigns/posts/{post_id}")
    assert del_res.status_code == 204

    # Post is gone
    assert client.get(f"/api/v1/campaigns/posts/{post_id}").status_code == 404


def test_queue_post_missing_schedule_time_returns_422(client: TestClient):
    account_id = _create_account_via_api(client, "fail_bot")
    camp_res = client.post("/api/v1/campaigns/", json={"name": "Post Test"})
    campaign_id = camp_res.json()["id"]

    # When status is "scheduled", scheduled_at is required by Pydantic model validator
    res = client.post(
        f"/api/v1/campaigns/{campaign_id}/posts",
        json={
            "account_id": account_id,
            "content": "Post without schedule time",
            "status": "scheduled",
        },
    )
    assert res.status_code == 422
    assert res.json()["error"] == "VALIDATION_ERROR"


def test_queue_post_under_inactive_campaign_returns_400(client: TestClient):
    account_id = _create_account_via_api(client, "archived_bot")
    camp_res = client.post(
        "/api/v1/campaigns/",
        json={"name": "Archived Camp", "status": "archived"},
    )
    campaign_id = camp_res.json()["id"]

    res = client.post(
        f"/api/v1/campaigns/{campaign_id}/posts",
        json={
            "account_id": account_id,
            "content": "Post should be rejected",
            "status": "draft",
        },
    )
    assert res.status_code == 400
    assert res.json()["error"] == "BAD_REQUEST"
