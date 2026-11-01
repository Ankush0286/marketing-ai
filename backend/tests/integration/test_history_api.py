from uuid import uuid4

from fastapi.testclient import TestClient


def test_create_and_get_activity_log_flow(client: TestClient):
    entity_id = str(uuid4())

    # 1. Record activity log via POST
    create_res = client.post(
        "/api/v1/history/",
        json={
            "activity_type": "campaign_created",
            "severity": "success",
            "title": "Q4 Growth Campaign Created",
            "description": "User created campaign targeting SaaS founders.",
            "entity_type": "campaign",
            "entity_id": entity_id,
            "actor": "user",
            "extra_metadata": {"tags": ["saas", "growth"]},
        },
    )
    assert create_res.status_code == 201
    data = create_res.json()
    assert data["activity_type"] == "campaign_created"
    assert data["severity"] == "success"
    assert data["entity_type"] == "campaign"
    assert data["entity_id"] == entity_id
    log_id = data["id"]

    # 2. Get specific log by ID via GET
    get_res = client.get(f"/api/v1/history/{log_id}")
    assert get_res.status_code == 200
    assert get_res.json()["id"] == log_id
    assert get_res.json()["title"] == "Q4 Growth Campaign Created"


def test_list_activity_logs_with_query_filters(client: TestClient):
    # Ingest multiple test events
    client.post(
        "/api/v1/history/",
        json={
            "activity_type": "post_published",
            "severity": "success",
            "title": "Post Published",
        },
    )
    client.post(
        "/api/v1/history/",
        json={
            "activity_type": "post_failed",
            "severity": "error",
            "title": "Post Dispatch Error",
            "description": "Rate limit exceeded on Twitter API",
        },
    )

    # 1. Query all logs
    all_res = client.get("/api/v1/history/")
    assert all_res.status_code == 200
    assert len(all_res.json()) >= 2

    # 2. Filter by severity=error
    error_res = client.get("/api/v1/history/?severity=error")
    assert error_res.status_code == 200
    error_items = error_res.json()
    assert len(error_items) >= 1
    assert all(item["severity"] == "error" for item in error_items)

    # 3. Filter by activity_type=post_published
    published_res = client.get("/api/v1/history/?activity_type=post_published")
    assert published_res.status_code == 200
    published_items = published_res.json()
    assert len(published_items) >= 1
    assert all(item["activity_type"] == "post_published" for item in published_items)


def test_get_nonexistent_activity_log_returns_404(client: TestClient):
    fake_uuid = "00000000-0000-0000-0000-000000000000"
    res = client.get(f"/api/v1/history/{fake_uuid}")
    assert res.status_code == 404
    assert res.json()["error"] == "NOT_FOUND"


def test_create_activity_log_invalid_payload_returns_422(client: TestClient):
    # Invalid request missing required 'title' and 'activity_type'
    res = client.post(
        "/api/v1/history/",
        json={"severity": "info"},
    )
    assert res.status_code == 422
    assert res.json()["error"] == "VALIDATION_ERROR"
