"""Writing audit entries."""

from __future__ import annotations

from decimal import Decimal

from audit.models import AuditLog

#: Fields never worth recording (noise) or unsafe to serialise.
SKIP_FIELDS = {"created_at", "updated_at", "password"}


def serialise(instance, fields=None) -> dict:
    """A JSON-safe snapshot of a model instance."""
    data = {}
    for field in instance._meta.concrete_fields:
        name = field.name
        if name in SKIP_FIELDS or (fields is not None and name not in fields):
            continue
        value = getattr(instance, field.attname, None)
        if isinstance(value, Decimal):
            value = str(value)
        elif hasattr(value, "isoformat"):
            value = value.isoformat()
        elif value is not None and not isinstance(value, str | int | float | bool | dict | list):
            value = str(value)
        data[name] = value
    return data


def record_audit(*, company, user, action, instance=None, before=None, after=None, model=None):
    """Append one entry to the audit trail. Never raises into business logic."""
    try:
        return AuditLog.objects.create(
            company=company,
            user=user if (user and getattr(user, "pk", None)) else None,
            action=action,
            model=model or (instance.__class__.__name__ if instance else ""),
            object_id=str(getattr(instance, "pk", "") or ""),
            before=before,
            after=after,
        )
    except Exception:  # pragma: no cover - auditing must never break a request
        return None
