# Workbook spec — `accounting_monthly.xlsx`

Reverse-engineered and **verified against the file on 2026-09-22** (formula pass +
`data_only=True` pass with openpyxl 3.1.5). This is the source of truth for the payroll
engine and the Excel report generator.

## Sheets (17)

| Sheet | Rows | Contents |
|---|---|---|
| `تقرير الرواتب` | 202 | master report — all employees, all branches |
| `فرع الاردنية`, `فرع الرواد`, `فرع الزقازيق`, `فرع السلام`, `مركز التجهيزات`, `مركز الاتصالات`, `الادارة المالية`, `التشغيل` | 80 each | one per branch, same columns |
| `شرايط قبض <branch>` (8) | 309 each | payslip strips: 4 rows per employee |

Every sheet has `sheet_view.rightToLeft = True`.

## Master sheet geometry

- **Row 1** — title merged `A1:AG1` (note: `AH` is *outside* the merge):
  `تقرير الرواتب عن شهر فبراير 2026`
- **Rows 2–3** — two-row header.
  - Group headers on row 2: `G2:O2` = `الاستحقاق`, `P2:AE2` = `الاستقطاع`
  - Vertical merges across rows 2–3: `A2:A3`, `B2:B3`, `C2:C3`, `D2:D3`, `E2:E3`,
    `F2:F3`, `AF2:AF3`
- **Row 4** — blank spacer.
- **Rows 5–27** — 23 employees.
- **Rows 28–200** — blank template rows that still carry the formulas.
- **Row 201** — `الاجماليات` (SUM), **row 202** — `الإجمالي` (SUBTOTAL 9).
- `freeze_panes = "G15"` in the file.

## Columns

Data row `r`. `master` = employee master data, `monthly input` = aggregated from daily
records, `monthly amount` = summed `MonthlyAdjustment` rows, `calc` = formula.

| Col | Arabic header | Field | Type | Formula (row 5 verbatim) |
|---|---|---|---|---|
| A | الكود | `employee_code` | master | — |
| B | الاسم | `name` | master | — |
| C | الفرع | `branch` | master | — |
| D | الوظيفة | `job_title` | master | — |
| E | ساعات العمل | `daily_hours` | master (default 9) | — |
| F | الراتب | `base_salary` | master | — |
| G | ايام العمل | `work_days` | monthly input | — |
| H | قيمة ايام العمل | `work_days_value` | calc | `=+F5/30*G5` |
| I | الاضافى بالساعات | `overtime_hours` | monthly input | — |
| J | قيمة الاضافى | `overtime_value` | calc | `=+I5*F5/30/E5` |
| K | بدل اجازات | `leave_allowance_days` | monthly input | — |
| L | قيمة بدل الاجازات | `leave_allowance_value` | calc | `=+K5*F5/30` |
| M | مكافأة | `bonus` | monthly amount | — |
| N | اخرى | `other_earnings` | monthly amount | — |
| O | اجمالى الاستحقاق | `total_earnings` | calc | `=+N5+M5+L5+J5+H5` |
| P | ساعات التاخير | `late_hours` | monthly input | — |
| Q | قيمة ساعات التأخير | `late_value` | calc | `=+F5/30/E5*P5` |
| R | سلف | `advances` | monthly amount | — |
| S | سلفة مرحله | `carried_advance` | monthly amount | — |
| T | جزاء ادارى | `admin_penalty_days` | monthly input | — |
| U | قيمة الجزاء الادارى | `admin_penalty_value` | calc | `=+F5/30*T5` |
| V | جزاء البصمه | `fingerprint_penalty_days` | monthly input | — |
| W | قيمة جزاء البصمه | `fingerprint_penalty_value` | calc | `=+H5/30*V5` ← **H, not F** |
| X | غياب بدون اذن | `unexcused_absence_days` | monthly input | — |
| Y | جزاء غياب بدون اذن | `unexcused_absence_value` | calc | `=+F5/30*X5*1` |
| Z | المرضى | `sick_days` | monthly input | — |
| AA | قيمة المرضى | `sick_value` | calc | `=+(F5/30*Z5)*0.25` |
| AB | الراتب التاميني | `insurable_salary` | master/monthly | — |
| AC | تأمينات وضرائب | `insurance_and_tax` | calc | `=AB5*11%` |
| AD | الانحرافات | `deviations` | monthly amount | — |
| AE | عجز منتجات& عهدة | `shortage_custody` | monthly amount | — |
| AF | اجمالى الاستقطاع | `total_deductions` | calc | `=+AE5+AD5+Y5+U5+R5+Q5+AA5+S5+W5+AC5` |
| AG | صافى الراتب | `net_salary` | calc | `=+O5-AF5` |
| AH | ملاحظات | `notes` | text | — |

## Totals rows

Row 201 `الاجماليات` is `=SUM(<col>5:<col>200)` for every numeric column **except**:

- `O201` = `=+N201+M201+L201+J201+H201` (recomposed from the component totals, not a SUM)
- `AD201` — **has no formula at all** (a gap in the workbook)

Row 202 `الإجمالي` is `=SUBTOTAL(9,<col>5:<col>200)` for every numeric column **except**:

- `E202` = `=SUBTOTAL(9,E5:E201)` (range ends at 201, unlike every other column)
- `AG202` = `=+O202-AF202`
- `AH202` = `=SUM(F202-AG202)` — base-salary total minus net-pay total

## Quirks to preserve (do not silently "fix")

| Quirk | Policy field | Default |
|---|---|---|
| Month is always 30 days regardless of calendar length | `month_day_basis` | `30` |
| Overtime pays 1× the hourly rate, no statutory premium | `overtime_multiplier` | `1` |
| Fingerprint penalty is based on **earned days value (H)**, every other day-based item on base salary (F) | `fingerprint_penalty_base` | `"earned"` |
| Unexcused absence multiplier (the literal `*1`) | `absence_multiplier` | `1` |
| Sick day deducts 25% of a day | `sick_deduction_rate` | `0.25` |
| Insurance is a flat 11% of the insurable salary; **no income tax exists in the workbook** | `insurance_employee_rate` | `0.11` |
| Egyptian income tax brackets | `income_tax_enabled` | `False` |
| Default daily hours | `default_daily_hours` | `9` |

Precision: the workbook keeps full precision in cells. Store computed values at 6 dp;
round to 2 dp with `ROUND_HALF_UP` only at presentation and in the `#,##0.00` format.

## Golden fixture — February 2026, 23 employees

Verified cached values from `تقرير الرواتب`:

| Total | Value |
|---|---|
| `F` base salary | `162,500.00` |
| `O` total earnings | `156,959.26` (`156959.25925925927`) |
| `AF` total deductions | `42,220.37` (`42220.37037037037`) |
| `AG` total net | `114,738.89` (`114738.88888888889`) |

Other verified column totals: `G`=605, `H`=145,366.666667, `I`=204, `J`=5,592.592593,
`K`=0, `L`=0, `M`=6,000, `N`=0, `P`=35, `Q`=837.037037, `R`=37,485, `S`=0, `T`=8,
`U`=1,833.333333, `V`=0, `W`=0, `X`=3, `Y`=600, `Z`=0, `AA`=0, `AB`=0, `AC`=0,
`AE`=1,465.

Spot checks (all confirmed against cached values):

| Row | Inputs | Expected |
|---|---|---|
| 5 (employee 1) | F=7000, E=9, G=29, I=12, R=1600 | H=6766.67, J=311.11, O=7077.78, AF=1600, AG=5477.78 |
| 9 (employee 6) | F=6500, G=29, I=2, P=2, R=3300, T=2, AE=700 | O=6331.48, AF=4481.48, AG=1850.00 |
| 11 (employee 8) | F=6000, G=26, P=7, R=1030, X=3 | Y=600.00, AF=1785.56, AG=3414.44 |

## Payslip strip sheets

4 rows per employee, starting at row 2: group-header row, sub-header row, data row
(same formulas as the master sheet), blank spacer. So employee *n* occupies rows
`2 + 4(n-1)` … `5 + 4(n-1)`.

## Known defects in the source file

These are data-entry artifacts, not rules. The generator should emit the corrected
form; they are listed so nobody "discovers" them again.

1. `A2` (the code column header) contains the literal `'3 +'` instead of `الكود`. The
   strip sheets have `الكود` in the same position, confirming the intent.
2. `AD201` has no `SUM` formula, so `الانحرافات` is missing from the `الاجماليات` row.
3. `AG2:AG3` and `AH2:AH3` are **not** merged, unlike the other single-column headers.
4. `E202` sums `E5:E201`, one row further than every other `SUBTOTAL`.
5. The first strip block's header row omits `G` = `الاستحقاق`; later blocks include it.
6. All 8 branch sheets are empty and share a stale title,
   `مرتبات الاردنيه عن شهر 1-2025`, while the master sheet is February 2026.
7. Every one of the 23 employees is in branch `فرع اسماعليه`, which has **no sheet of
   its own**; the 8 branch sheets cover branches with no employees in this month.
8. Strip data has drifted from the master sheet — e.g. employee `4` (مريم) has
   `R = 815` on the strip but no advance on the master sheet.
