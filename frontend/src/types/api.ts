/** Shapes returned by the Django API. Money always arrives as a string. */

export type Locale = 'ar' | 'en';
export type Role = 'company_admin' | 'branch_entry';
export type PeriodStatus = 'open' | 'calculated' | 'closed';
export type AttendanceStatus =
  'present' | 'unexcused_absence' | 'sick' | 'paid_leave' | 'weekly_off' | 'excused_absence';

export type AdjustmentKind =
  | 'bonus'
  | 'other_earning'
  | 'advance'
  | 'carried_advance'
  | 'deviation'
  | 'shortage_custody'
  | 'leave_allowance_days';

export interface BranchBrief {
  id: number;
  name_ar: string;
  name_en: string;
}

export interface Membership {
  id: number;
  company_id: number;
  company_name_ar: string;
  company_name_en: string;
  company_slug: string;
  role: Role;
  branches: BranchBrief[];
}

export interface SessionUser {
  id: number;
  email: string;
  full_name: string;
  preferred_language: Locale;
  is_platform_admin: boolean;
  memberships: Membership[];
}

export interface Paginated<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface Branch {
  id: number;
  name_ar: string;
  name_en: string;
  code: string;
  is_active: boolean;
  employee_count?: number;
}

export interface Employee {
  id: number;
  code: string;
  name_ar: string;
  name_en: string;
  branch: number;
  branch_name: string;
  job_title: string;
  national_id: string;
  hire_date: string | null;
  termination_date: string | null;
  daily_hours: string;
  base_salary: string;
  insurable_salary: string;
  is_active: boolean;
}

export interface SalaryHistoryEntry {
  id: number;
  employee: number;
  base_salary: string;
  insurable_salary: string;
  effective_from: string;
  note: string;
}

export interface DailyRecord {
  id: number;
  employee: number;
  employee_code: string;
  employee_name: string;
  branch_id: number;
  date: string;
  status: AttendanceStatus;
  overtime_hours: string;
  late_hours: string;
  admin_penalty_days: string;
  fingerprint_penalty_days: string;
  note: string;
}

export interface DayCompletion {
  date: string;
  recorded: number;
  expected: number;
  complete: boolean;
}

export interface Period {
  id: number;
  year: number;
  month: number;
  label: string;
  status: PeriodStatus;
  calculated_at: string | null;
  closed_at: string | null;
  line_count?: number;
}

/** One row of the review grid — column letters match the Excel workbook. */
export interface PayrollLine {
  id: number;
  employee: number;
  employee_code: string; // A
  employee_name: string; // B
  branch_snapshot: string; // C
  job_title_snapshot: string; // D
  daily_hours: string; // E
  base_salary: string; // F
  work_days: string; // G
  work_days_value: string; // H
  overtime_hours: string; // I
  overtime_value: string; // J
  leave_allowance_days: string; // K
  leave_allowance_value: string; // L
  bonus: string; // M
  other_earnings: string; // N
  total_earnings: string; // O
  late_hours: string; // P
  late_value: string; // Q
  advances: string; // R
  carried_advance: string; // S
  admin_penalty_days: string; // T
  admin_penalty_value: string; // U
  fingerprint_penalty_days: string; // V
  fingerprint_penalty_value: string; // W
  unexcused_absence_days: string; // X
  unexcused_absence_value: string; // Y
  sick_days: string; // Z
  sick_value: string; // AA
  insurable_salary: string; // AB
  insurance_and_tax: string; // AC
  deviations: string; // AD
  shortage_custody: string; // AE
  total_deductions: string; // AF
  net_salary: string; // AG
  notes: string; // AH
  overrides: Record<string, string>;
  warnings: string[];
}

export type PeriodTotals = Record<string, string> & { employee_count: number };

export interface PeriodLinesResponse {
  period: Period;
  results: PayrollLine[];
  totals: PeriodTotals;
  by_branch: Record<string, PeriodTotals>;
  branches: string[];
}

export interface MonthlyAdjustment {
  id: number;
  period: number;
  employee: number;
  employee_code: string;
  employee_name: string;
  kind: AdjustmentKind;
  amount: string;
  note: string;
}

export interface Loan {
  id: number;
  employee: number;
  employee_code: string;
  employee_name: string;
  total: string;
  monthly_installment: string;
  remaining: string;
  start_year: number;
  start_month: number;
  is_active: boolean;
  note: string;
}

export interface DashboardBranch {
  branch_id: number;
  branch: string;
  employees: number;
  recorded: number;
  expected: number;
  completion: number;
}

export interface DashboardAlert {
  level: 'info' | 'warning';
  code: string;
  count: number;
}

export interface DashboardSummary {
  year: number;
  month: number;
  period: Period | null;
  status: PeriodStatus;
  employees: number;
  branches: number;
  completion: number;
  recorded: number;
  expected: number;
  per_branch: DashboardBranch[];
  totals: PeriodTotals | Record<string, never>;
  alerts: DashboardAlert[];
}

export interface PayrollPolicy {
  id?: number;
  effective_from: string;
  month_day_basis: number;
  overtime_multiplier: string;
  absence_multiplier: string;
  sick_deduction_rate: string;
  insurance_employee_rate: string;
  fingerprint_penalty_base: 'earned' | 'base';
  default_daily_hours: string;
  income_tax_enabled: boolean;
}

export interface Company {
  id: number;
  name_ar: string;
  name_en: string;
  slug: string;
  is_active: boolean;
  report_emails: string[];
  report_day: number;
  report_language: Locale;
  branch_count?: number;
  employee_count?: number;
  created_at?: string;
}

export interface ReportFile {
  id: number;
  period: number;
  period_label: string;
  kind: 'xlsx' | 'pdf';
  file_url: string | null;
  size: number;
  generated_at: string;
  emailed_to: string[];
  emailed_at: string | null;
}
