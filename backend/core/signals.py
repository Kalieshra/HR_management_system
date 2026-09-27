"""Cache invalidation: any change to pay-affecting data clears the aggregates."""

from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from attendance.models import DailyRecord
from companies.models import PayrollPolicy
from companies.services import invalidate_policy_cache
from employees.models import Employee
from payroll.models import MonthlyAdjustment, PayrollLine
from payroll.services.cache import invalidate_company_cache


@receiver(post_save, sender=DailyRecord)
@receiver(post_delete, sender=DailyRecord)
@receiver(post_save, sender=MonthlyAdjustment)
@receiver(post_delete, sender=MonthlyAdjustment)
@receiver(post_save, sender=PayrollLine)
@receiver(post_delete, sender=PayrollLine)
@receiver(post_save, sender=Employee)
@receiver(post_delete, sender=Employee)
def clear_company_aggregates(sender, instance, **kwargs):
    company_id = getattr(instance, "company_id", None)
    if company_id:
        invalidate_company_cache(company_id)


@receiver(post_save, sender=PayrollPolicy)
@receiver(post_delete, sender=PayrollPolicy)
def clear_policy_cache(sender, instance, **kwargs):
    if instance.company_id:
        invalidate_policy_cache(instance.company_id)
