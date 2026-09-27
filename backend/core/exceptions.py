"""Project-wide DRF exception handling."""

from django.utils.translation import gettext as _
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

from payroll.services.runner import PeriodClosedError


def api_exception_handler(exc, context):
    """Map domain errors onto HTTP status codes.

    A write against a closed period is a conflict, not a validation error —
    the client should reopen the month rather than fix its payload.
    """
    if isinstance(exc, PeriodClosedError):
        return Response(
            {"detail": str(exc) or _("This period is closed.")},
            status=status.HTTP_409_CONFLICT,
        )
    return exception_handler(exc, context)
