from fastapi.testclient import TestClient


def test_create_and_get_account_flow(client: TestClient):
    payload = {
        "platform": "twitter",
        "handle": "integration_bot",
        "display_name": "Integration Bot",
        "daily_post_limit": 5,
        "access_token": "token_to_encrypt",
    }

    # 1. POST create
    response = client.post("/api/v1/accounts/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["handle"] == "integration_bot"
    assert data["daily_post_limit"] == 5
    assert "id" in data
    account_id = data["id"]

    # Verify sensitive token is excluded from response
    assert "access_token" not in data
    assert "encrypted_access_token" not in data

    # 2. GET by ID
    get_response = client.get(f"/api/v1/accounts/{account_id}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == account_id


def test_list_and_filter_accounts_api(client: TestClient):
    client.post(
        "/api/v1/accounts/",
        json={"platform": "twitter", "handle": "list_bot_1"},
    )
    res2 = client.post(
        "/api/v1/accounts/",
        json={"platform": "instagram", "handle": "list_bot_2"},
    )
    acc2_id = res2.json()["id"]

    # Deactivate second account
    client.patch(f"/api/v1/accounts/{acc2_id}", json={"is_active": False})

    # List all
    all_res = client.get("/api/v1/accounts/")
    assert all_res.status_code == 200
    assert len(all_res.json()) == 2

    # List active only
    active_res = client.get("/api/v1/accounts/?active_only=true")
    assert active_res.status_code == 200
    assert len(active_res.json()) == 1
    assert active_res.json()[0]["handle"] == "list_bot_1"


def test_patch_account_api(client: TestClient):
    res = client.post(
        "/api/v1/accounts/",
        json={"platform": "twitter", "handle": "patch_bot", "daily_post_limit": 5},
    )
    account_id = res.json()["id"]

    patch_res = client.patch(
        f"/api/v1/accounts/{account_id}",
        json={"display_name": "Updated Name", "daily_post_limit": 15},
    )
    assert patch_res.status_code == 200
    updated_data = patch_res.json()
    assert updated_data["display_name"] == "Updated Name"
    assert updated_data["daily_post_limit"] == 15


def test_delete_account_api(client: TestClient):
    res = client.post(
        "/api/v1/accounts/",
        json={"platform": "twitter", "handle": "delete_bot"},
    )
    account_id = res.json()["id"]

    # Delete returns 204
    del_res = client.delete(f"/api/v1/accounts/{account_id}")
    assert del_res.status_code == 204

    # Subsequent GET returns 404
    get_res = client.get(f"/api/v1/accounts/{account_id}")
    assert get_res.status_code == 404


def test_create_duplicate_account_returns_409(client: TestClient):
    payload = {
        "platform": "instagram",
        "handle": "brand_official",
    }
    res1 = client.post("/api/v1/accounts/", json=payload)
    assert res1.status_code == 201

    res2 = client.post("/api/v1/accounts/", json=payload)
    assert res2.status_code == 409
    assert res2.json()["error"] == "CONFLICT"


def test_get_nonexistent_account_returns_404(client: TestClient):
    random_uuid = "00000000-0000-0000-0000-000000000000"
    response = client.get(f"/api/v1/accounts/{random_uuid}")
    assert response.status_code == 404
    assert response.json()["error"] == "NOT_FOUND"


def test_invalid_payload_returns_422(client: TestClient):
    payload = {
        "platform": "twitter",
        "handle": "invalid handle with spaces!",
    }
    response = client.post("/api/v1/accounts/", json=payload)
    assert response.status_code == 422
    assert response.json()["error"] == "VALIDATION_ERROR"
