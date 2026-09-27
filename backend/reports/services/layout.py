"""Column layout shared by the Excel generator and its verification test.

This is the single definition of the workbook's shape: which Excel column each
field lives in, what the Arabic and English headers are, and which columns are
inputs versus live formulas. See `docs/reference/workbook-spec.md`.
"""

from __future__ import annotations

from dataclasses import dataclass

MASTER_SHEET_AR = "تقرير الرواتب"
STRIP_PREFIX_AR = "شرايط قبض"

TITLE_ROW = 1
HEADER_TOP_ROW = 2
HEADER_SUB_ROW = 3
FIRST_DATA_ROW = 5  # row 4 is the workbook's blank spacer

GROUP_EARNINGS_AR = "الاستحقاق"
GROUP_DEDUCTIONS_AR = "الاستقطاع"
TOTALS_LABEL_AR = "الاجماليات"
SUBTOTAL_LABEL_AR = "الإجمالي"

GROUP_EARNINGS_EN = "Earnings"
GROUP_DEDUCTIONS_EN = "Deductions"
TOTALS_LABEL_EN = "Totals"
SUBTOTAL_LABEL_EN = "Grand total"

ARABIC_MONTHS = {
    1: "يناير",
    2: "فبراير",
    3: "مارس",
    4: "ابريل",
    5: "مايو",
    6: "يونيو",
    7: "يوليو",
    8: "اغسطس",
    9: "سبتمبر",
    10: "اكتوبر",
    11: "نوفمبر",
    12: "ديسمبر",
}


@dataclass(frozen=True)
class Column:
    letter: str
    index: int  # 1-based
    field: str | None  # PayrollLine attribute, None for computed-only
    header_ar: str
    header_en: str
    width: float
    kind: str  # "text" | "number" | "money" | "formula"
    #: Formula template with `{r}` for the row and policy placeholders.
    formula: str | None = None
    #: Part of the two-row header group (earnings G..O, deductions P..AE).
    group: str | None = None

    @property
    def is_numeric(self) -> bool:
        return self.kind in {"number", "money", "formula"}


# fmt: off
COLUMNS: tuple[Column, ...] = (
    Column("A", 1, "employee_code", "الكود", "Code", 8, "text"),
    Column("B", 2, "employee_name", "الاسم", "Name", 28, "text"),
    Column("C", 3, "branch_snapshot", "الفرع", "Branch", 16, "text"),
    Column("D", 4, "job_title_snapshot", "الوظيفة", "Job title", 16, "text"),
    Column("E", 5, "daily_hours", "ساعات العمل", "Daily hours", 10, "number"),
    Column("F", 6, "base_salary", "الراتب", "Salary", 12, "money"),

    Column("G", 7, "work_days", "ايام العمل", "Work days", 10, "number", group="earnings"),
    Column("H", 8, None, "قيمة ايام العمل", "Work days value", 14, "formula",
           "=+F{r}/{basis}*G{r}", group="earnings"),
    Column("I", 9, "overtime_hours", "الاضافى بالساعات", "Overtime hours", 12, "number",
           group="earnings"),
    Column("J", 10, None, "قيمة الاضافى", "Overtime value", 13, "formula",
           "=+I{r}*F{r}/{basis}/E{r}{ot}", group="earnings"),
    Column("K", 11, "leave_allowance_days", "بدل اجازات", "Leave allowance", 11, "number",
           group="earnings"),
    Column("L", 12, None, "قيمة بدل الاجازات", "Leave allowance value", 15, "formula",
           "=+K{r}*F{r}/{basis}", group="earnings"),
    Column("M", 13, "bonus", "مكافأة", "Bonus", 11, "money", group="earnings"),
    Column("N", 14, "other_earnings", "اخرى", "Other", 11, "money", group="earnings"),
    Column("O", 15, None, "اجمالى الاستحقاق", "Total earnings", 15, "formula",
           "=+N{r}+M{r}+L{r}+J{r}+H{r}", group="earnings"),

    Column("P", 16, "late_hours", "ساعات التاخير", "Late hours", 12, "number",
           group="deductions"),
    Column("Q", 17, None, "قيمة ساعات التأخير", "Late value", 15, "formula",
           "=+F{r}/{basis}/E{r}*P{r}", group="deductions"),
    Column("R", 18, "advances", "سلف", "Advances", 11, "money", group="deductions"),
    Column("S", 19, "carried_advance", "سلفة مرحله", "Carried advance", 12, "money",
           group="deductions"),
    Column("T", 20, "admin_penalty_days", "جزاء ادارى", "Admin penalty", 11, "number",
           group="deductions"),
    Column("U", 21, None, "قيمة الجزاء الادارى", "Admin penalty value", 16, "formula",
           "=+F{r}/{basis}*T{r}", group="deductions"),
    Column("V", 22, "fingerprint_penalty_days", "جزاء البصمه", "Fingerprint penalty", 12,
           "number", group="deductions"),
    Column("W", 23, None, "قيمة جزاء البصمه", "Fingerprint penalty value", 16, "formula",
           "=+{fp}{r}/{basis}*V{r}", group="deductions"),
    Column("X", 24, "unexcused_absence_days", "غياب بدون اذن", "Unexcused absence", 13,
           "number", group="deductions"),
    Column("Y", 25, None, "جزاء غياب بدون اذن", "Unexcused absence value", 16, "formula",
           "=+F{r}/{basis}*X{r}*{absence}", group="deductions"),
    Column("Z", 26, "sick_days", "المرضى", "Sick days", 10, "number", group="deductions"),
    Column("AA", 27, None, "قيمة المرضى", "Sick value", 12, "formula",
           "=+(F{r}/{basis}*Z{r})*{sick}", group="deductions"),
    Column("AB", 28, "insurable_salary", "الراتب التاميني", "Insurable salary", 13, "money",
           group="deductions"),
    Column("AC", 29, None, "تأمينات وضرائب", "Insurance & tax", 13, "formula",
           "=AB{r}*{insurance}%", group="deductions"),
    Column("AD", 30, "deviations", "الانحرافات", "Deviations", 11, "money", group="deductions"),
    Column("AE", 31, "shortage_custody", "عجز منتجات& عهدة", "Shortage / custody", 14, "money",
           group="deductions"),

    Column("AF", 32, None, "اجمالى الاستقطاع", "Total deductions", 15, "formula",
           "=+AE{r}+AD{r}+Y{r}+U{r}+R{r}+Q{r}+AA{r}+S{r}+W{r}+AC{r}"),
    Column("AG", 33, None, "صافى الراتب", "Net salary", 14, "formula", "=+O{r}-AF{r}"),
    Column("AH", 34, "notes", "ملاحظات", "Notes", 20, "text"),
)
# fmt: on

BY_LETTER = {column.letter: column for column in COLUMNS}
BY_FIELD = {column.field: column for column in COLUMNS if column.field}

#: PayrollLine attribute each formula column corresponds to, for verification.
FORMULA_FIELD = {
    "H": "work_days_value",
    "J": "overtime_value",
    "L": "leave_allowance_value",
    "O": "total_earnings",
    "Q": "late_value",
    "U": "admin_penalty_value",
    "W": "fingerprint_penalty_value",
    "Y": "unexcused_absence_value",
    "AA": "sick_value",
    "AC": "insurance_and_tax",
    "AF": "total_deductions",
    "AG": "net_salary",
}

FIRST_GROUP_COLUMN = "G"
LAST_EARNINGS_COLUMN = "O"
FIRST_DEDUCTION_COLUMN = "P"
LAST_DEDUCTION_COLUMN = "AE"
LAST_TITLE_COLUMN = "AG"


def numeric_columns() -> tuple[Column, ...]:
    return tuple(column for column in COLUMNS if column.is_numeric)
