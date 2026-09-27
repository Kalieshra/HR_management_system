"""Celery tasks for payroll."""

from celery import shared_task

from payroll.models import Period
from payroll.services.runner import run_period


@shared_task(name="payroll.calculate_period")
def calculate_period_task(period_id: int, user_id: int | None = None) -> dict:
    """Recalculate a period in the background (used above ~50 employees)."""
    from accounts.models import User

    period = Period.all_objects.select_related("company").get(pk=period_id)
    user = User.objects.filter(pk=user_id).first() if user_id else None
    lines = run_period(period, user=user)
    return {"period_id": period_id, "lines": len(lines), "status": period.status}
