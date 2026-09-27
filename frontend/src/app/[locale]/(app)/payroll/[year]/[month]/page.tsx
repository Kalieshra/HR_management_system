'use client';

import { useMutation } from '@tanstack/react-query';
import type { CellValueChangedEvent, ColDef, ColGroupDef } from 'ag-grid-community';
import { Calculator, Download, FileText, Loader2, Lock, Mail, Unlock } from 'lucide-react';
import { useLocale, useTranslations } from 'next-intl';
import { useParams } from 'next/navigation';
import { useMemo, useState } from 'react';
import { toast } from 'sonner';

import { DataGrid } from '@/components/data/grid';
import { EmptyState } from '@/components/empty-state';
import { PageHeader } from '@/components/page-header';
import { QueryBoundary } from '@/components/query-boundary';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { useInvalidateCompany, usePeriodLines, usePeriods } from '@/hooks/use-api';
import { ApiError, api } from '@/lib/api';
import { formatMoney, monthName, type Locale } from '@/lib/format';
import { useCompany } from '@/providers/company-provider';
import type { PayrollLine, PeriodTotals, ReportFile } from '@/types/api';

const ALL = '__all__';

/** Inputs a company admin may override directly in the grid. */
const EDITABLE: ReadonlySet<keyof PayrollLine> = new Set([
  'work_days',
  'overtime_hours',
  'leave_allowance_days',
  'bonus',
  'other_earnings',
  'late_hours',
  'advances',
  'carried_advance',
  'admin_penalty_days',
  'fingerprint_penalty_days',
  'unexcused_absence_days',
  'sick_days',
  'insurable_salary',
  'deviations',
  'shortage_custody',
] as Array<keyof PayrollLine>);

const MONEY_COLUMNS: ReadonlySet<string> = new Set([
  'base_salary',
  'work_days_value',
  'overtime_value',
  'leave_allowance_value',
  'bonus',
  'other_earnings',
  'total_earnings',
  'late_value',
  'advances',
  'carried_advance',
  'admin_penalty_value',
  'fingerprint_penalty_value',
  'unexcused_absence_value',
  'sick_value',
  'insurable_salary',
  'insurance_and_tax',
  'deviations',
  'shortage_custody',
  'total_deductions',
  'net_salary',
]);

const IDENTITY_COLUMNS = [
  'employee_code',
  'employee_name',
  'branch_snapshot',
  'job_title_snapshot',
  'daily_hours',
  'base_salary',
] as const;

const EARNINGS_COLUMNS = [
  'work_days',
  'work_days_value',
  'overtime_hours',
  'overtime_value',
  'leave_allowance_days',
  'leave_allowance_value',
  'bonus',
  'other_earnings',
  'total_earnings',
] as const;

const DEDUCTION_COLUMNS = [
  'late_hours',
  'late_value',
  'advances',
  'carried_advance',
  'admin_penalty_days',
  'admin_penalty_value',
  'fingerprint_penalty_days',
  'fingerprint_penalty_value',
  'unexcused_absence_days',
  'unexcused_absence_value',
  'sick_days',
  'sick_value',
  'insurable_salary',
  'insurance_and_tax',
  'deviations',
  'shortage_custody',
] as const;

const TAIL_COLUMNS = ['total_deductions', 'net_salary', 'notes'] as const;

export default function PayrollReviewPage() {
  const t = useTranslations('payroll');
  const tc = useTranslations('common');
  const tr = useTranslations('reports');
  const locale = useLocale() as Locale;
  const params = useParams<{ year: string; month: string }>();
  const invalidate = useInvalidateCompany();
  const { isCompanyAdmin } = useCompany();

  const year = Number(params.year);
  const month = Number(params.month);

  const { data: periods = [] } = usePeriods();
  const period = periods.find((item) => item.year === year && item.month === month) ?? null;

  const [branch, setBranch] = useState<string>(ALL);
  const { data, isLoading, error } = usePeriodLines(period?.id ?? null);

  const closed = period?.status === 'closed';

  const onApiError = (err: unknown) =>
    toast.error(
      err instanceof ApiError
        ? err.isPeriodClosed
          ? tc('periodClosed')
          : err.message
        : tc('genericError'),
    );

  const recalculate = useMutation({
    mutationFn: () =>
      api.post<{ lines?: number; queued: boolean; employees?: number }>(
        `/api/v1/periods/${period?.id}/calculate/`,
      ),
    onSuccess: (result) => {
      toast.success(
        result.queued
          ? t('queued', { count: result.employees ?? 0 })
          : t('calculated', { count: result.lines ?? 0 }),
      );
      invalidate();
    },
    onError: onApiError,
  });

  const close = useMutation({
    mutationFn: () => api.post(`/api/v1/periods/${period?.id}/close/`),
    onSuccess: () => {
      toast.success(t('closedOk'));
      invalidate();
    },
    onError: onApiError,
  });

  const reopen = useMutation({
    mutationFn: () => api.post(`/api/v1/periods/${period?.id}/reopen/`),
    onSuccess: () => {
      toast.success(t('reopenedOk'));
      invalidate();
    },
    onError: onApiError,
  });

  const makeFile = useMutation({
    mutationFn: (kind: 'xlsx' | 'payslips') =>
      api.post<ReportFile>(`/api/v1/reports/${period?.id}/${kind}/`),
    onSuccess: (report) => {
      toast.success(tr('generated'));
      invalidate();
      if (report.file_url) window.open(report.file_url, '_blank', 'noopener');
    },
    onError: onApiError,
  });

  const emailReport = useMutation({
    mutationFn: () =>
      api.post<{ sent: number; recipients: string[] }>(`/api/v1/reports/${period?.id}/email/`),
    onSuccess: (result) => {
      toast.success(tr('sent', { count: result.recipients.length }));
      invalidate();
    },
    onError: onApiError,
  });

  const override = useMutation({
    mutationFn: ({ id, field, value }: { id: number; field: string; value: string }) =>
      api.patch<PayrollLine>(`/api/v1/lines/${id}/`, { [field]: value }),
    onSuccess: () => {
      toast.success(tc('saved'));
      invalidate();
    },
    onError: onApiError,
  });

  const rows = useMemo(() => {
    const all = data?.results ?? [];
    return branch === ALL ? all : all.filter((line) => line.branch_snapshot === branch);
  }, [data, branch]);

  const totals: PeriodTotals | undefined =
    branch === ALL ? data?.totals : data?.by_branch?.[branch];

  const column = (field: string, extra: Partial<ColDef<PayrollLine>> = {}): ColDef<PayrollLine> => {
    const isMoney = MONEY_COLUMNS.has(field);
    const editable = isCompanyAdmin && !closed && EDITABLE.has(field as keyof PayrollLine);
    return {
      field: field as keyof PayrollLine,
      headerName: t(`columns.${field}`),
      width: isMoney ? 130 : 120,
      editable,
      cellClass: (params) => {
        const classes =
          isMoney || field.endsWith('_days') || field.endsWith('_hours') ? ['numeric'] : [];
        if (params.data?.overrides?.[field] !== undefined) classes.push('cell-overridden');
        return classes;
      },
      tooltipValueGetter: (params) => {
        const original = params.data?.overrides?.[field];
        return original === undefined ? undefined : t('overridden', { original });
      },
      valueFormatter: isMoney ? (params) => formatMoney(params.value as string, locale) : undefined,
      ...extra,
    };
  };

  const columns = useMemo<(ColDef<PayrollLine> | ColGroupDef<PayrollLine>)[]>(
    () => [
      ...IDENTITY_COLUMNS.map((field) =>
        column(field, {
          pinned: locale === 'ar' ? 'right' : 'left',
          width: field === 'employee_name' ? 190 : field === 'employee_code' ? 90 : 130,
        }),
      ),
      {
        headerName: t('groups.earnings'),
        children: EARNINGS_COLUMNS.map((field) => column(field)),
      },
      {
        headerName: t('groups.deductions'),
        children: DEDUCTION_COLUMNS.map((field) => column(field)),
      },
      ...TAIL_COLUMNS.map((field) => column(field, { width: field === 'notes' ? 200 : 140 })),
    ],
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [locale, isCompanyAdmin, closed, t],
  );

  const onCellValueChanged = (event: CellValueChangedEvent<PayrollLine>) => {
    const field = event.colDef.field;
    if (!field || !event.data) return;
    override.mutate({ id: event.data.id, field, value: String(event.newValue ?? 0) });
  };

  return (
    <>
      <PageHeader
        title={t('title')}
        description={t('subtitle', { month: monthName(month, locale), year })}
        actions={
          isCompanyAdmin && period ? (
            <>
              <Badge variant={closed ? 'default' : 'secondary'}>
                {tc(`periodStatus.${period.status}`)}
              </Badge>
              <Button
                variant="outline"
                onClick={() => recalculate.mutate()}
                disabled={closed || recalculate.isPending}
              >
                {recalculate.isPending ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                ) : (
                  <Calculator className="size-4" aria-hidden />
                )}
                {t('recalculate')}
              </Button>
              {closed ? (
                <Button
                  variant="outline"
                  onClick={() => reopen.mutate()}
                  disabled={reopen.isPending}
                >
                  <Unlock className="size-4" aria-hidden />
                  {t('reopen')}
                </Button>
              ) : (
                <Button onClick={() => close.mutate()} disabled={close.isPending}>
                  <Lock className="size-4" aria-hidden />
                  {t('close')}
                </Button>
              )}
              <Button
                variant="outline"
                onClick={() => makeFile.mutate('xlsx')}
                disabled={makeFile.isPending}
              >
                <Download className="size-4" aria-hidden />
                {t('downloadExcel')}
              </Button>
              <Button
                variant="outline"
                onClick={() => makeFile.mutate('payslips')}
                disabled={makeFile.isPending}
              >
                <FileText className="size-4" aria-hidden />
                {t('downloadPayslips')}
              </Button>
              <Button
                variant="outline"
                onClick={() => emailReport.mutate()}
                disabled={emailReport.isPending}
              >
                <Mail className="size-4" aria-hidden />
                {t('emailReport')}
              </Button>
            </>
          ) : null
        }
      />

      {data && data.branches.length > 1 ? (
        <Tabs value={branch} onValueChange={setBranch} className="mb-4">
          <TabsList>
            <TabsTrigger value={ALL}>{t('allBranches')}</TabsTrigger>
            {data.branches.map((name) => (
              <TabsTrigger key={name} value={name}>
                {name}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      ) : null}

      <QueryBoundary isLoading={isLoading} error={error}>
        {rows.length === 0 ? (
          <EmptyState title={t('noLines')} description={t('noLinesHint')} />
        ) : (
          <>
            <DataGrid<PayrollLine>
              rowData={rows}
              columnDefs={columns}
              getRowId={(params) => String(params.data.id)}
              onCellValueChanged={onCellValueChanged}
              tooltipShowDelay={200}
              enableCellTextSelection
              height={Math.min(620, 160 + rows.length * 38)}
            />

            {totals ? (
              <div
                className="mt-4 grid gap-3 rounded-md border bg-muted/40 p-4 sm:grid-cols-2 xl:grid-cols-4"
                data-testid="payroll-totals"
              >
                {(
                  [
                    ['base_salary', t('columns.base_salary')],
                    ['total_earnings', t('columns.total_earnings')],
                    ['total_deductions', t('columns.total_deductions')],
                    ['net_salary', t('columns.net_salary')],
                  ] as const
                ).map(([field, label]) => (
                  <div key={field} className="space-y-1">
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
                    <p className="numeric text-lg font-bold" data-testid={`total-${field}`}>
                      {formatMoney(totals[field], locale)}
                    </p>
                  </div>
                ))}
              </div>
            ) : null}
          </>
        )}
      </QueryBoundary>
    </>
  );
}
