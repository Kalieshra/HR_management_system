"""Pytest bootstrap for the backend test suite."""

import django
import pytest
from django.conf import settings
from django.core.cache import cache
from rest_framework.test import APIClient


def pytest_configure() -> None:
    # PBKDF2 costs ~0.5s per hash by design; the suite creates hundreds of
    # users and logs in constantly, so tests use a deliberately cheap hasher.
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

    # Tests get their own Redis database. Sharing db 0 with the dev stack let
    # login-throttle counters leak between tests, which made whole files fail
    # only when run together.
    settings.CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": settings.CACHES["default"]["LOCATION"].rsplit("/", 1)[0] + "/9",
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
            "KEY_PREFIX": "hrms-test",
        }
    }
    django.setup()


@pytest.fixture(autouse=True)
def clear_cache():
    """Every test starts with an empty cache: no stale aggregates, no throttle debt."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api() -> APIClient:
    """Unauthenticated DRF client."""
    return APIClient()


@pytest.fixture
def reference_workbook_path():
    """Path to the source-of-truth Excel workbook used by parity tests."""
    path = settings.REFERENCE_WORKBOOK
    if not path.exists():
        pytest.fail(f"Reference workbook missing at {path}")
    return path
