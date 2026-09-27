"""Seed a demo company straight from the reference workbook.

Creates the tenant, its branches, a default payroll policy, the 23 employees of
`تقرير الرواتب`, and a February 2026 period whose calculated lines reproduce the
workbook's numbers exactly — so the UI and the Excel agree cell for cell.

Attendance note: the workbook pays 29 or 30 work days in a month that has only
28 calendar days (its basis is always 30). Daily records therefore cannot
reproduce column G on their own, so the seeder writes realistic daily records
*and* records the workbook's monthly figures as explicit overrides — exactly the
path a company takes when it enters monthly totals instead of daily data.
"""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from accounts.models import Membership, Role, User
from attendance.models import AttendanceStatus, DailyRecord
from companies.models import Branch, Company, PayrollPolicy
from companies.services import delete_company_data
from employees.models import Employee, SalaryHistory
from payroll.models import AdjustmentKind, MonthlyAdjustment, PayrollLine, Period
from payroll.services.runner import run_period
from payroll.services.workbook import load_reference

DEMO_SLUG = "demo"
DEMO_YEAR = 2026
DEMO_MONTH = 2
POLICY_FROM = date(2020, 1, 1)

#: The 8 branch sheets in the workbook. The employees all sit in فرع اسماعليه,
#: which has no sheet of its own — both are created so the demo mirrors reality.
TEMPLATE_BRANCHES = [
    "فرع الاردنية",
    "فرع الرواد",
    "فرع الزقازيق",
    "فرع السلام",
    "مركز التجهيزات",
    "مركز الاتصالات",
    "الادارة المالية",
    "التشغيل",
]

DEMO_USERS = [
    ("owner@hrms.test", "Platform Owner", None, True),
    ("admin@demo.test", "مدير الشركة", Role.COMPANY_ADMIN, False),
    ("entry@demo.test", "مدخل بيانات", Role.BRANCH_ENTRY, False),
]
DEMO_PASSWORD = "DemoPass!2026"

#: Inputs that come from attendance and must be overridden to match the sheet.
ATTENDANCE_INPUTS = (
    "work_days",
    "overtime_hours",
    "late_hours",
    "admin_penalty_days",
    "fingerprint_penalty_days",
    "unexcused_absence_days",
    "sick_days",
)

#: Inputs that are entered as monthly amounts.
ADJUSTMENT_INPUTS = {
    "bonus": AdjustmentKind.BONUS,
    "other_earnings": AdjustmentKind.OTHER_EARNING,
    "advances": AdjustmentKind.ADVANCE,
    "carried_advance": AdjustmentKind.CARRIED_ADVANCE,
    "deviations": AdjustmentKind.DEVIATION,
    "shortage_custody": AdjustmentKind.SHORTAGE_CUSTODY,
    "leave_allowance_days": AdjustmentKind.LEAVE_ALLOWANCE_DAYS,
}


class Command(BaseCommand):
    help = "Create a demo company seeded from docs/reference/accounting_monthly.xlsx"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete the existing demo company before seeding.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        path = settings.REFERENCE_WORKBOOK
        if not path.exists():
            raise CommandError(f"Reference workbook not found at {path}")

        data = load_reference(path)
        if not data.rows:
            raise CommandError("Reference workbook contained no employee rows.")

        if options["reset"]:
            existing = Company.objects.filter(slug=DEMO_SLUG).first()
            if existing is not None:
                delete_company_data(existing)
                self.stdout.write("Removed the previous demo company.")

        company = self._create_company()
        branches = self._create_branches(company, data)
        self._create_policy(company)
        users = self._create_users(company, branches)
        employees = self._create_employees(company, branches, data)
        period = self._create_period(company)
        self._seed_attendance(company, period, employees, data)
        self._seed_adjustments(company, period, employees, data, users["admin"])
        self._calculate_with_overrides(period, employees, data, users["admin"])

        self._report(company, period, data)

    # -- building blocks ---------------------------------------------------

    def _create_company(self) -> Company:
        company, created = Company.objects.get_or_create(
            slug=DEMO_SLUG,
            defaults={
                "name_ar": "الشركة التجريبية",
                "name_en": "Demo Company",
                "report_emails": ["admin@demo.test"],
                "report_day": 5,
            },
        )
        self.stdout.write(f"{'Created' if created else 'Reusing'} company {company}")
        return company

    def _create_branches(self, company, data) -> dict[str, Branch]:
        names = []
        for row in data.rows:
            if row.branch and row.branch not in names:
                names.append(row.branch)
        names.extend(name for name in TEMPLATE_BRANCHES if name not in names)

        branches = {}
        for index, name in enumerate(names, start=1):
            branch, _ = Branch.all_objects.get_or_create(
                company=company,
                name_ar=name,
                defaults={"code": f"B{index:02d}", "name_en": slugify(name) or f"branch-{index}"},
            )
            branches[name] = branch
        self.stdout.write(f"Branches: {len(branches)}")
        return branches

    def _create_policy(self, company) -> PayrollPolicy:
        policy, _ = PayrollPolicy.all_objects.get_or_create(
            company=company,
            effective_from=POLICY_FROM,
        )
        return policy

    def _create_users(self, company, branches) -> dict[str, User]:
        created = {}
        for email, name, role, is_platform in DEMO_USERS:
            user, is_new = User.objects.get_or_create(
                email=email,
                defaults={"full_name": name, "is_platform_admin": is_platform},
            )
            # Always reset the demo password: the seeder is meant to be re-run,
            # and a known password is the whole point of a demo account.
            user.set_password(DEMO_PASSWORD)
            user.full_name = name
            user.is_platform_admin = is_platform
            user.is_staff = is_platform
            user.is_superuser = is_platform
            user.save()
            del is_new

            if role:
                membership, _ = Membership.objects.get_or_create(
                    user=user, company=company, defaults={"role": role}
                )
                if role == Role.BRANCH_ENTRY:
                    membership.branches.set(list(branches.values())[:1])
            created["owner" if is_platform else email.split("@")[0]] = user
        return created

    def _create_employees(self, company, branches, data) -> dict[str, Employee]:
        employees = {}
        for row in data.rows:
            branch = branches.get(row.branch) or next(iter(branches.values()))
            employee, _ = Employee.all_objects.update_or_create(
                company=company,
                code=row.code,
                defaults={
                    "branch": branch,
                    "name_ar": row.name,
                    "job_title": row.job_title,
                    "daily_hours": row.inputs["daily_hours"] or Decimal("9"),
                    "base_salary": row.inputs["base_salary"],
                    "insurable_salary": row.inputs["insurable_salary"],
                    "is_active": True,
                    "hire_date": date(2024, 1, 1),
                },
            )
            SalaryHistory.all_objects.get_or_create(
                company=company,
                employee=employee,
                effective_from=POLICY_FROM,
                defaults={
                    "base_salary": row.inputs["base_salary"],
                    "insurable_salary": row.inputs["insurable_salary"],
                    "note": "Seeded from the reference workbook",
                },
            )
            employees[row.code] = employee
        self.stdout.write(f"Employees: {len(employees)}")
        return employees

    def _create_period(self, company) -> Period:
        period, _ = Period.all_objects.get_or_create(
            company=company, year=DEMO_YEAR, month=DEMO_MONTH
        )
        return period

    def _seed_attendance(self, company, period, employees, data) -> None:
        """Write one daily record per calendar day, shaped by the sheet's counts."""
        days_in_month = calendar.monthrange(DEMO_YEAR, DEMO_MONTH)[1]
        first = date(DEMO_YEAR, DEMO_MONTH, 1)

        DailyRecord.all_objects.filter(
            company=company, date__gte=first, date__lte=period.end_date
        ).delete()

        records = []
        for row in data.rows:
            employee = employees[row.code]
            absent = int(row.inputs["unexcused_absence_days"])
            sick = int(row.inputs["sick_days"])
            overtime = row.inputs["overtime_hours"]
            late = row.inputs["late_hours"]
            admin_penalty = row.inputs["admin_penalty_days"]
            fingerprint = row.inputs["fingerprint_penalty_days"]

            statuses = []
            for offset in range(days_in_month):
                day = first + timedelta(days=offset)
                if day.weekday() == calendar.FRIDAY:
                    statuses.append((day, AttendanceStatus.WEEKLY_OFF))
                else:
                    statuses.append((day, AttendanceStatus.PRESENT))

            working = [i for i, (_, s) in enumerate(statuses) if s == AttendanceStatus.PRESENT]
            for index in working[:absent]:
                statuses[index] = (statuses[index][0], AttendanceStatus.UNEXCUSED_ABSENCE)
            for index in working[absent : absent + sick]:
                statuses[index] = (statuses[index][0], AttendanceStatus.SICK)

            present = [i for i, (_, s) in enumerate(statuses) if s == AttendanceStatus.PRESENT]
            spread = len(present) or 1

            for position, (day, status) in enumerate(statuses):
                is_present = status == AttendanceStatus.PRESENT
                share = Decimal(1) / spread if is_present else Decimal(0)
                records.append(
                    DailyRecord(
                        company=company,
                        employee=employee,
                        date=day,
                        status=status,
                        overtime_hours=(overtime * share).quantize(Decimal("0.01")),
                        late_hours=(late * share).quantize(Decimal("0.01")),
                        admin_penalty_days=(
                            (admin_penalty if position == present[0] and is_present else Decimal(0))
                            if present
                            else Decimal(0)
                        ),
                        fingerprint_penalty_days=(
                            (fingerprint if position == present[0] and is_present else Decimal(0))
                            if present
                            else Decimal(0)
                        ),
                    )
                )

        DailyRecord.all_objects.bulk_create(records, batch_size=500)
        self.stdout.write(f"Daily records: {len(records)}")

    def _seed_adjustments(self, company, period, employees, data, user) -> None:
        MonthlyAdjustment.all_objects.filter(company=company, period=period).delete()

        rows = []
        for row in data.rows:
            employee = employees[row.code]
            for field_name, kind in ADJUSTMENT_INPUTS.items():
                amount = row.inputs[field_name]
                if amount == 0:
                    continue
                rows.append(
                    MonthlyAdjustment(
                        company=company,
                        period=period,
                        employee=employee,
                        kind=kind,
                        amount=amount,
                        note="Seeded from the reference workbook",
                        created_by=user,
                    )
                )
        MonthlyAdjustment.all_objects.bulk_create(rows)
        self.stdout.write(f"Monthly adjustments: {len(rows)}")

    def _calculate_with_overrides(self, period, employees, data, user) -> None:
        """Run once, pin the workbook's attendance figures, run again."""
        run_period(period, user=user)

        lines = {
            line.employee_id: line
            for line in PayrollLine.all_objects.filter(company=period.company, period=period)
        }

        for row in data.rows:
            line = lines[employees[row.code].pk]
            overrides = {}
            for field_name in ATTENDANCE_INPUTS:
                target = row.inputs[field_name]
                if getattr(line, field_name) != target:
                    overrides[field_name] = str(getattr(line, field_name))
                    setattr(line, field_name, target)
            if overrides:
                line.overrides = overrides
                line.save(update_fields=[*ATTENDANCE_INPUTS, "overrides", "updated_at"])

        run_period(period, user=user)

    # -- output ------------------------------------------------------------

    def _report(self, company, period, data) -> None:
        lines = PayrollLine.all_objects.filter(company=company, period=period)
        totals = {
            "base_salary": sum(line.base_salary for line in lines),
            "total_earnings": sum(line.total_earnings for line in lines),
            "total_deductions": sum(line.total_deductions for line in lines),
            "net_salary": sum(line.net_salary for line in lines),
        }

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Seeded {company} — {period.arabic_label}"))
        self.stdout.write(f"  lines            {lines.count()}")
        for key, value in totals.items():
            expected = data.totals.get(key, Decimal("0"))
            delta = abs(Decimal(value) - expected)
            marker = "OK " if delta <= Decimal("0.01") else "DIFF"
            self.stdout.write(f"  {marker} {key:<18} {value:>14,.2f}   workbook {expected:>14,.2f}")

        self.stdout.write("")
        self.stdout.write("Sign in with:")
        for email, _name, role, is_platform in DEMO_USERS:
            label = "platform admin" if is_platform else role
            self.stdout.write(f"  {email:<20} {DEMO_PASSWORD}   ({label})")
