'use client';

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/lib/api';
import { useCompany } from '@/providers/company-provider';
import type {
  Branch,
  DashboardSummary,
  DayCompletion,
  Employee,
  Loan,
  MonthlyAdjustment,
  Paginated,
  PayrollPolicy,
  Period,
  PeriodLinesResponse,
  ReportFile,
} from '@/types/api';

/** Every cache key is namespaced by company so switching tenants can't bleed. */
function key(companyId: number | null, ...parts: unknown[]) {
  return ['company', companyId, ...parts];
}

function qs(params: Record<string, string | number | boolean | undefined | null>) {
  const search = new URLSearchParams();
  for (const [name, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') search.set(name, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : '';
}

export function useDashboard(year: number, month: number) {
  const { companyId } = useCompany();
  return useQuery({
    queryKey: key(companyId, 'dashboard', year, month),
    queryFn: () => api.get<DashboardSummary>(`/api/v1/dashboard/summary${qs({ year, month })}`),
    enabled: companyId !== null,
  });
}

export function useBranches() {
  const { companyId } = useCompany();
  return useQuery({
    queryKey: key(companyId, 'branches'),
    queryFn: () => api.get<Paginated<Branch>>('/api/v1/branches/?page_size=200'),
    enabled: companyId !== null,
    select: (data) => data.results,
  });
}

export function useEmployees(
  filters: { branch?: number | ''; search?: string; is_active?: boolean } = {},
) {
  const { companyId } = useCompany();
  return useQuery({
    queryKey: key(companyId, 'employees', filters),
    queryFn: () =>
      api.get<Paginated<Employee>>(
        `/api/v1/employees/${qs({
          page_size: 500,
          branch: filters.branch || undefined,
          search: filters.search || undefined,
          is_active: filters.is_active === undefined ? undefined : String(filters.is_active),
        })}`,
      ),
    enabled: companyId !== null,
    select: (data) => data.results,
  });
}

export function usePeriods() {
  const { companyId } = useCompany();
  return useQuery({
    queryKey: key(companyId, 'periods'),
    queryFn: () => api.get<Paginated<Period>>('/api/v1/periods/?page_size=100'),
    enabled: companyId !== null,
    select: (data) => data.results,
  });
}

export function usePeriodLines(periodId: number | null, branch?: string) {
  const { companyId } = useCompany();
  return useQuery({
    queryKey: key(companyId, 'period-lines', periodId, branch ?? 'all'),
    queryFn: () =>
      api.get<PeriodLinesResponse>(`/api/v1/periods/${periodId}/lines/${qs({ branch })}`),
    enabled: companyId !== null && periodId !== null,
  });
}

export function useAdjustments(periodId: number | null) {
  const { companyId } = useCompany();
  return useQuery({
    queryKey: key(companyId, 'adjustments', periodId),
    queryFn: () =>
      api.get<Paginated<MonthlyAdjustment>>(
        `/api/v1/adjustments/${qs({ period: periodId ?? undefined, page_size: 500 })}`,
      ),
    enabled: companyId !== null && periodId !== null,
    select: (data) => data.results,
  });
}

export function useLoans() {
  const { companyId } = useCompany();
  return useQuery({
    queryKey: key(companyId, 'loans'),
    queryFn: () => api.get<Paginated<Loan>>('/api/v1/loans/?page_size=500'),
    enabled: companyId !== null,
    select: (data) => data.results,
  });
}

export function useDailyRecords(date: string, branch?: number | '') {
  const { companyId } = useCompany();
  return useQuery({
    queryKey: key(companyId, 'daily-records', date, branch ?? 'all'),
    queryFn: () =>
      api.get<Paginated<import('@/types/api').DailyRecord>>(
        `/api/v1/daily-records/${qs({ date, branch: branch || undefined, page_size: 500 })}`,
      ),
    enabled: companyId !== null && Boolean(date),
    select: (data) => data.results,
  });
}

export function useCalendar(year: number, month: number, branch?: number | '') {
  const { companyId } = useCompany();
  return useQuery({
    queryKey: key(companyId, 'calendar', year, month, branch ?? 'all'),
    queryFn: () =>
      api.get<DayCompletion[]>(
        `/api/v1/daily-records/calendar/${qs({ year, month, branch: branch || undefined })}`,
      ),
    enabled: companyId !== null,
  });
}

export function usePolicy() {
  const { companyId } = useCompany();
  return useQuery({
    queryKey: key(companyId, 'policy'),
    queryFn: () => api.get<PayrollPolicy>('/api/v1/policy/current/'),
    enabled: companyId !== null,
  });
}

export function useReports() {
  const { companyId } = useCompany();
  return useQuery({
    queryKey: key(companyId, 'reports'),
    queryFn: () => api.get<Paginated<ReportFile>>('/api/v1/reports/?page_size=100'),
    enabled: companyId !== null,
    select: (data) => data.results,
  });
}

/** Invalidate every query for the active company after a write. */
export function useInvalidateCompany() {
  const queryClient = useQueryClient();
  const { companyId } = useCompany();
  return () => queryClient.invalidateQueries({ queryKey: ['company', companyId] });
}

export { key as companyQueryKey, qs as queryString };
export { useMutation };
