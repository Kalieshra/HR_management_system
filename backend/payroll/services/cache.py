"""Redis cache keys for the read-heavy payroll screens."""

from django.core.cache import cache

DASHBOARD_TTL = 600  # 10 minutes
LINES_TTL = 600


def dashboard_key(company_id: int, year: int, month: int) -> str:
    return f"dashboard:{company_id}:{year}:{month}"


def lines_totals_key(company_id: int, period_id: int) -> str:
    return f"lines-totals:{company_id}:{period_id}"


def invalidate_company_cache(company_id: int) -> None:
    """Drop every cached aggregate for a company.

    Called from signals whenever a DailyRecord, MonthlyAdjustment, PayrollLine
    or Employee changes, so the dashboard and totals never go stale.
    """
    try:
        cache.delete_pattern(f"*dashboard:{company_id}:*")
        cache.delete_pattern(f"*lines-totals:{company_id}:*")
    except AttributeError:  # pragma: no cover - non-redis cache backend
        cache.clear()
