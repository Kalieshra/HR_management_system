"""Phase 1 smoke tests: the service answers and its dependencies are wired."""

import pytest
from django.urls import reverse


def test_health_is_public_and_reports_ok(api):
    """Liveness must answer without auth and without touching the database."""
    response = api.get(reverse("core:health"))

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "hrms-backend"


@pytest.mark.django_db
def test_ready_reports_database_and_cache(api):
    """Readiness proves PostgreSQL and Redis are both reachable."""
    response = api.get(reverse("core:ready"))

    body = response.json()
    assert body["components"] == {"database": "ok", "cache": "ok"}, body
    assert body["status"] == "ok"
    assert response.status_code == 200


def test_openapi_schema_builds(api):
    """drf-spectacular must be able to generate the schema for every route."""
    response = api.get("/api/schema/?format=json")

    assert response.status_code == 200
    assert "/api/v1/health/" in response.json()["paths"]
