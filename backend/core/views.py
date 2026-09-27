"""Operational endpoints.

`health/` is a dependency-free liveness probe; `health/ready/` additionally
verifies that PostgreSQL and Redis answer, and is what docker/compose or a load
balancer should poll before routing traffic.
"""

from django.core.cache import cache
from django.db import connection
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

APP_VERSION = "0.1.0"


class HealthView(APIView):
    """Liveness: the process is up and able to serve a request."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(
        summary="Liveness probe",
        responses={200: dict},
        tags=["ops"],
    )
    def get(self, request: Request) -> Response:
        return Response(
            {
                "status": "ok",
                "service": "hrms-backend",
                "version": APP_VERSION,
                "time": timezone.now().isoformat(),
            }
        )


class ReadyView(APIView):
    """Readiness: PostgreSQL and Redis are both reachable."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(
        summary="Readiness probe",
        responses={200: dict, 503: dict},
        tags=["ops"],
    )
    def get(self, request: Request) -> Response:
        components = {
            "database": _check(_ping_database),
            "cache": _check(_ping_cache),
        }
        healthy = all(value == "ok" for value in components.values())
        return Response(
            {
                "status": "ok" if healthy else "degraded",
                "components": components,
                "version": APP_VERSION,
            },
            status=status.HTTP_200_OK if healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        )


def _check(probe) -> str:
    try:
        probe()
    except Exception as exc:  # any failure of the probe is a failed check
        return f"error: {exc.__class__.__name__}"
    return "ok"


def _ping_database() -> None:
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
        cursor.fetchone()


def _ping_cache() -> None:
    cache.set("hrms:health", "1", timeout=10)
    if cache.get("hrms:health") != "1":
        raise RuntimeError(_("Cache round-trip failed."))
