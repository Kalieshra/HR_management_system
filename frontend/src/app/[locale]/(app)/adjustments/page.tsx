'use client';

import { useMutation } from '@tanstack/react-query';
import { Loader2, Plus, Trash2 } from 'lucide-react';
import { useLocale, useTranslations } from 'next-intl';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

import { EmptyState } from '@/components/empty-state';
import { PageHeader } from '@/components/page-header';
import { PeriodSelect } from '@/components/period-select';
import { QueryBoundary } from '@/components/query-boundary';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
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
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useAdjustments, useEmployees, useInvalidateCompany, usePeriods } from '@/hooks/use-api';
import { ApiError, api } from '@/lib/api';
import { formatMoney, type Locale } from '@/lib/format';
import type { AdjustmentKind } from '@/types/api';

const KINDS: AdjustmentKind[] = [
  'bonus',
  'other_earning',
  'advance',
  'carried_advance',
  'deviation',
  'shortage_custody',
  'leave_allowance_days',
];

export default function AdjustmentsPage() {
  const t = useTranslations('adjustments');
  const tc = useTranslations('common');
  const locale = useLocale() as Locale;
  const invalidate = useInvalidateCompany();

  const { data: periods = [] } = usePeriods();
  const [periodId, setPeriodId] = useState<number | null>(null);
  useEffect(() => {
    if (periodId === null && periods.length > 0) setPeriodId(periods[0].id);
  }, [periods, periodId]);

  const { data: rows = [], isLoading, error } = useAdjustments(periodId);
  const { data: employees = [] } = useEmployees({ is_active: true });

  const [open, setOpen] = useState(false);
  const [employee, setEmployee] = useState('');
  const [kind, setKind] = useState<AdjustmentKind>('bonus');
  const [amount, setAmount] = useState('');
  const [note, setNote] = useState('');

  const onApiError = (err: unknown) =>
    toast.error(
      err instanceof ApiError
        ? err.isPeriodClosed
          ? tc('periodClosed')
          : err.message
        : tc('genericError'),
    );

  const create = useMutation({
    mutationFn: () =>
      api.post('/api/v1/adjustments/', {
        period: periodId,
        employee: Number(employee),
        kind,
        amount,
        note,
      }),
    onSuccess: () => {
      toast.success(tc('saved'));
      invalidate();
      setOpen(false);
      setAmount('');
      setNote('');
    },
    onError: onApiError,
  });

  const remove = useMutation({
    mutationFn: (id: number) => api.delete(`/api/v1/adjustments/${id}/`),
    onSuccess: () => {
      toast.success(tc('deleted'));
      invalidate();
    },
    onError: onApiError,
  });

  return (
    <>
      <PageHeader
        title={t('title')}
        description={t('subtitle')}
        actions={
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button disabled={periodId === null}>
                <Plus className="size-4" aria-hidden />
                {t('add')}
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{t('add')}</DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                <div className="space-y-1">
                  <Label htmlFor="adj-employee">{tc('employee')}</Label>
                  <Select value={employee} onValueChange={setEmployee}>
                    <SelectTrigger id="adj-employee">
                      <SelectValue placeholder={tc('employee')} />
                    </SelectTrigger>
                    <SelectContent>
                      {employees.map((item) => (
                        <SelectItem key={item.id} value={String(item.id)}>
                          {item.code} — {item.name_ar}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-1">
                  <Label htmlFor="adj-kind">{t('kind')}</Label>
                  <Select value={kind} onValueChange={(next) => setKind(next as AdjustmentKind)}>
                    <SelectTrigger id="adj-kind">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {KINDS.map((item) => (
                        <SelectItem key={item} value={item}>
                          {t(`kinds.${item}`)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>

                <div className="space-y-1">
                  <Label htmlFor="adj-amount">{tc('amount')}</Label>
                  <Input
                    id="adj-amount"
                    inputMode="decimal"
                    dir="ltr"
                    className="text-start"
                    value={amount}
                    onChange={(event) => setAmount(event.target.value)}
                  />
                </div>

                <div className="space-y-1">
                  <Label htmlFor="adj-note">{tc('note')}</Label>
                  <Input
                    id="adj-note"
                    value={note}
                    onChange={(event) => setNote(event.target.value)}
                  />
                </div>

                <div className="flex justify-end gap-2">
                  <Button variant="outline" onClick={() => setOpen(false)}>
                    {tc('cancel')}
                  </Button>
                  <Button
                    onClick={() => create.mutate()}
                    disabled={!employee || !amount || create.isPending}
                  >
                    {create.isPending ? (
                      <Loader2 className="size-4 animate-spin" aria-hidden />
                    ) : null}
                    {tc('save')}
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        }
      />

      <div className="mb-4">
        <PeriodSelect
          periods={periods}
          value={periodId}
          onChange={setPeriodId}
          label={t('period')}
        />
      </div>

      <QueryBoundary isLoading={isLoading} error={error}>
        {rows.length === 0 ? (
          <EmptyState title={t('empty')} />
        ) : (
          <div className="overflow-x-auto rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{tc('employee')}</TableHead>
                  <TableHead>{t('kind')}</TableHead>
                  <TableHead className="text-end">{tc('amount')}</TableHead>
                  <TableHead>{tc('note')}</TableHead>
                  <TableHead className="w-10" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row) => (
                  <TableRow key={row.id} data-testid="adjustment-row">
                    <TableCell>
                      <span className="numeric text-muted-foreground">{row.employee_code}</span>{' '}
                      {row.employee_name}
                    </TableCell>
                    <TableCell>{t(`kinds.${row.kind}`)}</TableCell>
                    <TableCell className="numeric text-end">
                      {formatMoney(row.amount, locale)}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{row.note}</TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label={tc('delete')}
                        onClick={() => remove.mutate(row.id)}
                      >
                        <Trash2 className="size-4 text-destructive" aria-hidden />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </QueryBoundary>
    </>
  );
}
