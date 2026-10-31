from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.common.exceptions import (
    AuthenticationFailedError,
    RateLimitExceededError,
)
from app.main import app

# Renamed from test_router to avoid PytestCollectionWarning
error_mock_router = APIRouter(prefix="/test-errors")


@error_mock_router.get("/rate-limit")
def trigger_rate_limit():
    raise RateLimitExceededError("Daily limit hit")


@error_mock_router.get("/unauthorized")
def trigger_unauthorized():
    raise AuthenticationFailedError("Bad API credentials")


@error_mock_router.get("/unhandled")
def trigger_unhandled():
    raise RuntimeError("Unexpected failure")


app.include_router(error_mock_router)


def test_rate_limit_maps_to_429(client: TestClient):
    res = client.get("/test-errors/rate-limit")
    assert res.status_code == 429
    assert res.json()["error"] == "RATE_LIMIT_EXCEEDED"
    assert res.json()["detail"] == "Daily limit hit"


def test_auth_failed_maps_to_401(client: TestClient):
    res = client.get("/test-errors/unauthorized")
    assert res.status_code == 401
    assert res.json()["error"] == "UNAUTHORIZED"
    assert res.json()["detail"] == "Bad API credentials"


def test_unhandled_exception_maps_to_500(client: TestClient):
    res = client.get("/test-errors/unhandled")
    assert res.status_code == 500
    assert res.json()["error"] == "INTERNAL_SERVER_ERROR"
