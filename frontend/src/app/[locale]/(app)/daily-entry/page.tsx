'use client';

import { useMutation } from '@tanstack/react-query';
import type { CellValueChangedEvent, ColDef } from 'ag-grid-community';
import { CalendarCheck, Check, Copy, Loader2 } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { toast } from 'sonner';

import { DataGrid } from '@/components/data/grid';
import { EmptyState } from '@/components/empty-state';
import { PageHeader } from '@/components/page-header';
import { QueryBoundary } from '@/components/query-boundary';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  useBranches,
  useCalendar,
  useDailyRecords,
  useEmployees,
  useInvalidateCompany,
} from '@/hooks/use-api';
import { ApiError, api } from '@/lib/api';
import { isoDate } from '@/lib/format';
import { cn } from '@/lib/utils';
import type { AttendanceStatus } from '@/types/api';

const ALL = 'all';
const AUTOSAVE_MS = 900;

const STATUSES: AttendanceStatus[] = [
  'present',
  'unexcused_absence',
  'sick',
  'paid_leave',
  'weekly_off',
  'excused_absence',
];

interface Row {
  employee: number;
  code: string;
  name: string;
  branch: string;
  status: AttendanceStatus;
  overtime_hours: number;
  late_hours: number;
  admin_penalty_days: number;
  fingerprint_penalty_days: number;
  note: string;
}

export default function DailyEntryPage() {
  const t = useTranslations('dailyEntry');
  const tc = useTranslations('common');
  const te = useTranslations('employees');
  const invalidate = useInvalidateCompany();

  const [date, setDate] = useState(() => isoDate(new Date()));
  const [branch, setBranch] = useState<string>(ALL);
  const [rows, setRows] = useState<Row[]>([]);
  const [dirty, setDirty] = useState<Set<number>>(new Set());
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const branchId = branch === ALL ? '' : Number(branch);
  const { data: branches = [] } = useBranches();
  const {
    data: employees = [],
    isLoading: loadingEmployees,
    error: employeesError,
  } = useEmployees({ branch: branchId, is_active: true });
  const { data: records = [], isLoading: loadingRecords } = useDailyRecords(date, branchId);

  const [year, month] = date.split('-').map(Number);
  const { data: calendar = [] } = useCalendar(year, month, branchId);

  // One row per employee, pre-filled from whatever is already saved for the day.
  useEffect(() => {
    const byEmployee = new Map(records.map((record) => [record.employee, record]));
    setRows(
      employees.map((employee) => {
        const record = byEmployee.get(employee.id);
        return {
          employee: employee.id,
          code: employee.code,
          name: employee.name_ar,
          branch: employee.branch_name,
          status: record?.status ?? 'present',
          overtime_hours: Number(record?.overtime_hours ?? 0),
          late_hours: Number(record?.late_hours ?? 0),
          admin_penalty_days: Number(record?.admin_penalty_days ?? 0),
          fingerprint_penalty_days: Number(record?.fingerprint_penalty_days ?? 0),
          note: record?.note ?? '',
        };
      }),
    );
    setDirty(new Set());
  }, [employees, records]);

  const save = useMutation({
    mutationFn: (payload: Row[]) =>
      api.post<{ saved: number }>('/api/v1/daily-records/bulk/', {
        rows: payload.map((row) => ({
          employee: row.employee,
          date,
          status: row.status,
          overtime_hours: String(row.overtime_hours ?? 0),
          late_hours: String(row.late_hours ?? 0),
          admin_penalty_days: String(row.admin_penalty_days ?? 0),
          fingerprint_penalty_days: String(row.fingerprint_penalty_days ?? 0),
          note: row.note ?? '',
        })),
      }),
    onSuccess: () => {
      setDirty(new Set());
      invalidate();
    },
    onError: (error) => {
      toast.error(
        error instanceof ApiError
          ? error.isPeriodClosed
            ? tc('periodClosed')
            : error.message
          : tc('genericError'),
      );
    },
  });

  const queueSave = useCallback(
    (changed: Row[]) => {
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => save.mutate(changed), AUTOSAVE_MS);
    },
    [save],
  );

  const onCellValueChanged = useCallback(
    (event: CellValueChangedEvent<Row>) => {
      const row = event.data;
      if (!row) return;
      setRows((current) =>
        current.map((item) => (item.employee === row.employee ? { ...item, ...row } : item)),
      );
      setDirty((current) => new Set(current).add(row.employee));
      queueSave([row]);
    },
    [queueSave],
  );

  const markAllPresent = () => {
    const updated = rows.map((row) => ({ ...row, status: 'present' as AttendanceStatus }));
    setRows(updated);
    setDirty(new Set(updated.map((row) => row.employee)));
    queueSave(updated);
  };

  const copyYesterday = useMutation({
    mutationFn: () => {
      const previous = new Date(date);
      previous.setDate(previous.getDate() - 1);
      return api.post<{ copied: number }>('/api/v1/daily-records/copy-from/', {
        source_date: isoDate(previous),
        target_date: date,
      });
    },
    onSuccess: () => {
      toast.success(tc('saved'));
      invalidate();
    },
    onError: (error) =>
      toast.error(
        error instanceof ApiError && error.isPeriodClosed ? tc('periodClosed') : tc('genericError'),
      ),
  });

  const columns = useMemo<ColDef<Row>[]>(
    () => [
      { field: 'code', headerName: te('code'), width: 100 },
      { field: 'name', headerName: tc('employee'), flex: 2, minWidth: 180 },
      { field: 'branch', headerName: tc('branch'), flex: 1, minWidth: 130 },
      {
        field: 'status',
        headerName: t('status'),
        width: 175,
        editable: true,
        cellEditor: 'agSelectCellEditor',
        cellEditorParams: { values: STATUSES },
        valueFormatter: (params) => t(`statuses.${params.value as AttendanceStatus}`),
      },
      {
        field: 'overtime_hours',
        headerName: t('overtimeHours'),
        width: 130,
        editable: true,
        cellDataType: 'number',
        cellClass: 'numeric',
      },
      {
        field: 'late_hours',
        headerName: t('lateHours'),
        width: 125,
        editable: true,
        cellDataType: 'number',
        cellClass: 'numeric',
      },
      {
        field: 'admin_penalty_days',
        headerName: t('adminPenalty'),
        width: 150,
        editable: true,
        cellDataType: 'number',
        cellClass: 'numeric',
      },
      {
        field: 'fingerprint_penalty_days',
        headerName: t('fingerprintPenalty'),
        width: 170,
        editable: true,
        cellDataType: 'number',
        cellClass: 'numeric',
      },
      { field: 'note', headerName: t('note'), flex: 2, minWidth: 160, editable: true },
    ],
    [t, tc, te],
  );

  return (
    <>
      <PageHeader
        title={t('title')}
        description={t('subtitle')}
        actions={
          <>
            <Button variant="outline" onClick={markAllPresent} disabled={rows.length === 0}>
              <CalendarCheck className="size-4" aria-hidden />
              {t('markAllPresent')}
            </Button>
            <Button
              variant="outline"
              onClick={() => copyYesterday.mutate()}
              disabled={copyYesterday.isPending}
            >
              {copyYesterday.isPending ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <Copy className="size-4" aria-hidden />
              )}
              {t('copyYesterday')}
            </Button>
          </>
        }
      />

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <Label htmlFor="entry-date">{t('date')}</Label>
          <Input
            id="entry-date"
            type="date"
            value={date}
            onChange={(event) => setDate(event.target.value)}
            className="w-44"
            dir="ltr"
          />
        </div>

        <div className="space-y-1">
          <Label htmlFor="entry-branch">{t('branch')}</Label>
          <Select value={branch} onValueChange={setBranch}>
            <SelectTrigger id="entry-branch" className="w-52">
              <SelectValue placeholder={t('allBranches')} />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>{t('allBranches')}</SelectItem>
              {branches.map((item) => (
                <SelectItem key={item.id} value={String(item.id)}>
                  {item.name_ar}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <p
          className="flex items-center gap-2 pb-2 text-sm text-muted-foreground"
          aria-live="polite"
          data-testid="save-status"
        >
          {save.isPending ? (
            <>
              <Loader2 className="size-4 animate-spin" aria-hidden />
              {t('saving')}
            </>
          ) : dirty.size > 0 ? (
            t('unsaved')
          ) : (
            <>
              <Check className="size-4 text-emerald-600" aria-hidden />
              {t('saved')}
            </>
          )}
        </p>
      </div>

      {calendar.length > 0 ? (
        <div className="mb-4">
          <p className="mb-2 text-sm font-medium">{t('calendar')}</p>
          <div className="flex flex-wrap gap-1">
            {calendar.map((day) => {
              const dayNumber = Number(day.date.slice(-2));
              const isActive = day.date === date;
              return (
                <button
                  key={day.date}
                  type="button"
                  onClick={() => setDate(day.date)}
                  aria-current={isActive ? 'date' : undefined}
                  title={`${day.date} — ${day.recorded}/${day.expected}`}
                  className={cn(
                    'numeric h-8 w-8 rounded-md border text-xs transition-colors',
                    day.complete
                      ? 'border-emerald-600/40 bg-emerald-600/15 text-emerald-700'
                      : day.recorded > 0
                        ? 'border-amber-500/40 bg-amber-500/15 text-amber-700'
                        : 'text-muted-foreground hover:bg-accent',
                    isActive && 'ring-2 ring-primary',
                  )}
                >
                  {dayNumber}
                </button>
              );
            })}
          </div>
        </div>
      ) : null}

      <QueryBoundary isLoading={loadingEmployees || loadingRecords} error={employeesError}>
        {rows.length === 0 ? (
          <EmptyState title={t('noEmployees')} />
        ) : (
          <DataGrid<Row>
            rowData={rows}
            columnDefs={columns}
            getRowId={(params) => String(params.data.employee)}
            onCellValueChanged={onCellValueChanged}
            singleClickEdit
            enterNavigatesVertically
            enterNavigatesVerticallyAfterEdit
            height={Math.min(640, 130 + rows.length * 38)}
          />
        )}
      </QueryBoundary>
    </>
  );
}
