from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.common.enums import PlatformType
from app.modules.triggers.commands import EvaluateIncomingPostCommand
from app.modules.triggers.service import TriggerService


def _create_account_via_api(client: TestClient, handle: str = "api_trigger_bot") -> str:
    """Helper to register a connected account for rule association."""
    res = client.post(
        "/api/v1/accounts/",
        json={"platform": "twitter", "handle": handle},
    )
    assert res.status_code == 201
    return res.json()["id"]


# =============================================================================
# Watched Handles API Integration Tests
# =============================================================================


def test_watched_handle_api_lifecycle(client: TestClient):
    # 1. Add watched handle (testing leading @ sanitization)
    add_res = client.post(
        "/api/v1/triggers/handles",
        json={
            "platform": "twitter",
            "handle": "@competitor_founder",
            "display_name": "Competitor Founder",
            "scrape_frequency_minutes": 20,
        },
    )
    assert add_res.status_code == 201
    data = add_res.json()
    assert data["handle"] == "competitor_founder"  # Stripped @
    handle_id = data["id"]

    # 2. Get by ID
    get_res = client.get(f"/api/v1/triggers/handles/{handle_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == handle_id

    # 3. List
    list_res = client.get("/api/v1/triggers/handles")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 4. Patch
    patch_res = client.patch(
        f"/api/v1/triggers/handles/{handle_id}",
        json={"display_name": "Updated Founder", "scrape_frequency_minutes": 45},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["display_name"] == "Updated Founder"
    assert patch_res.json()["scrape_frequency_minutes"] == 45

    # 5. Delete
    del_res = client.delete(f"/api/v1/triggers/handles/{handle_id}")
    assert del_res.status_code == 204

    # 6. Verify 404
    assert client.get(f"/api/v1/triggers/handles/{handle_id}").status_code == 404


def test_create_duplicate_watched_handle_returns_409(client: TestClient):
    payload = {"platform": "twitter", "handle": "unique_brand"}
    res1 = client.post("/api/v1/triggers/handles", json=payload)
    assert res1.status_code == 201

    # Duplicate attempt with leading @
    res2 = client.post("/api/v1/triggers/handles", json={"platform": "twitter", "handle": "@unique_brand"})
    assert res2.status_code == 409
    assert res2.json()["error"] == "CONFLICT"


# =============================================================================
# Trigger Rules API Integration Tests
# =============================================================================


def test_trigger_rule_api_lifecycle(client: TestClient):
    account_id = _create_account_via_api(client, "rule_owner")

    # 1. Create rule
    create_res = client.post(
        "/api/v1/triggers/rules",
        json={
            "name": "Alternative Seeker",
            "platform": "twitter",
            "account_id": account_id,
            "action_type": "stage_draft",
            "keywords_any": ["alternative", "substitute", "#buildinpublic"],
            "keywords_all": ["looking"],
            "response_template": "Hey @{author}, check our project!",
            "cooldown_minutes": 45,
        },
    )
    assert create_res.status_code == 201
    rule_data = create_res.json()
    rule_id = rule_data["id"]
    assert rule_data["name"] == "Alternative Seeker"
    assert "#buildinpublic" in rule_data["keywords_any"]

    # 2. Get rule by ID
    get_res = client.get(f"/api/v1/triggers/rules/{rule_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == rule_id

    # 3. List rules
    list_res = client.get("/api/v1/triggers/rules?platform=twitter")
    assert list_res.status_code == 200
    assert len(list_res.json()) >= 1

    # 4. Patch rule
    patch_res = client.patch(
        f"/api/v1/triggers/rules/{rule_id}",
        json={"name": "Renamed Rule", "cooldown_minutes": 90},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["name"] == "Renamed Rule"
    assert patch_res.json()["cooldown_minutes"] == 90

    # 5. Delete rule
    del_res = client.delete(f"/api/v1/triggers/rules/{rule_id}")
    assert del_res.status_code == 204

    # 6. Verify 404
    assert client.get(f"/api/v1/triggers/rules/{rule_id}").status_code == 404


def test_create_rule_without_keywords_returns_422(client: TestClient):
    account_id = _create_account_via_api(client, "bad_rule_bot")
    res = client.post(
        "/api/v1/triggers/rules",
        json={
            "name": "No Keywords",
            "platform": "twitter",
            "account_id": account_id,
            "keywords_any": [],
            "keywords_all": [],
        },
    )
    assert res.status_code == 422
    assert res.json()["error"] == "VALIDATION_ERROR"


# =============================================================================
# Trigger Matches API Integration Tests
# =============================================================================


def test_list_and_review_matches_api(client: TestClient, db_session: Session):
    account_id = _create_account_via_api(client, "match_reviewer_bot")

    # 1. Create rule
    rule_res = client.post(
        "/api/v1/triggers/rules",
        json={
            "name": "Opportunity Catcher",
            "platform": "twitter",
            "account_id": account_id,
            "keywords_any": ["recommendation"],
            "response_template": "Hey @{author}, here is what we suggest!",
        },
    )
    rule_id = rule_res.json()["id"]

    # Ingest a simulated post directly through the isolated in-memory db_session fixture
    service = TriggerService(db_session)
    matches = service.evaluate_incoming_post(
        EvaluateIncomingPostCommand(
            platform=PlatformType.TWITTER,
            platform_post_id="tweet_opportunity_1",
            author_handle="prospective_buyer",
            post_content="Looking for a solid software recommendation.",
        )
    )
    match_id = str(matches[0].id)

    # 2. List matches via API
    list_res = client.get(f"/api/v1/triggers/matches?rule_id={rule_id}")
    assert list_res.status_code == 200
    match_items = list_res.json()
    assert len(match_items) == 1
    assert match_items[0]["author_handle"] == "prospective_buyer"
    assert match_items[0]["status"] == "pending_review"

    # 3. Review match (approve)
    review_res = client.post(
        f"/api/v1/triggers/matches/{match_id}/review",
        json={
            "status": "approved",
            "edited_response": "Hey @prospective_buyer, check our top-rated platform!",
        },
    )
    assert review_res.status_code == 200
    assert review_res.json()["status"] == "approved"
    assert review_res.json()["generated_response"] == "Hey @prospective_buyer, check our top-rated platform!"


def test_review_match_invalid_status_returns_422(client: TestClient):
    fake_uuid = "00000000-0000-0000-0000-000000000000"
    res = client.post(
        f"/api/v1/triggers/matches/{fake_uuid}/review",
        json={"status": "invalid_review_status"},
    )
    assert res.status_code == 422
    assert res.json()["error"] == "VALIDATION_ERROR"
