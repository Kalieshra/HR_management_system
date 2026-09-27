'use client';

import { useMutation } from '@tanstack/react-query';
import { Loader2, Plus } from 'lucide-react';
import { useLocale, useTranslations } from 'next-intl';
import { useState } from 'react';
import { toast } from 'sonner';

import { EmptyState } from '@/components/empty-state';
import { PageHeader } from '@/components/page-header';
import { QueryBoundary } from '@/components/query-boundary';
import { Badge } from '@/components/ui/badge';
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
import { useEmployees, useInvalidateCompany, useLoans } from '@/hooks/use-api';
import { ApiError, api } from '@/lib/api';
import { formatMoney, monthName, type Locale } from '@/lib/format';

export default function LoansPage() {
  const t = useTranslations('loans');
  const tc = useTranslations('common');
  const locale = useLocale() as Locale;
  const invalidate = useInvalidateCompany();

  const { data: loans = [], isLoading, error } = useLoans();
  const { data: employees = [] } = useEmployees({ is_active: true });

  const today = new Date();
  const [open, setOpen] = useState(false);
  const [employee, setEmployee] = useState('');
  const [total, setTotal] = useState('');
  const [installment, setInstallment] = useState('');
  const [startYear, setStartYear] = useState(String(today.getFullYear()));
  const [startMonth, setStartMonth] = useState(String(today.getMonth() + 1));

  const create = useMutation({
    mutationFn: () =>
      api.post('/api/v1/loans/', {
        employee: Number(employee),
        total,
        monthly_installment: installment,
        remaining: total,
        start_year: Number(startYear),
        start_month: Number(startMonth),
      }),
    onSuccess: () => {
      toast.success(tc('saved'));
      invalidate();
      setOpen(false);
      setTotal('');
      setInstallment('');
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : tc('genericError')),
  });

  return (
    <>
      <PageHeader
        title={t('title')}
        description={t('subtitle')}
        actions={
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button>
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
                  <Label htmlFor="loan-employee">{tc('employee')}</Label>
                  <Select value={employee} onValueChange={setEmployee}>
                    <SelectTrigger id="loan-employee">
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

                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <Label htmlFor="loan-total">{t('total')}</Label>
                    <Input
                      id="loan-total"
                      inputMode="decimal"
                      dir="ltr"
                      className="text-start"
                      value={total}
                      onChange={(event) => setTotal(event.target.value)}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="loan-installment">{t('installment')}</Label>
                    <Input
                      id="loan-installment"
                      inputMode="decimal"
                      dir="ltr"
                      className="text-start"
                      value={installment}
                      onChange={(event) => setInstallment(event.target.value)}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="loan-year">{tc('year')}</Label>
                    <Input
                      id="loan-year"
                      inputMode="numeric"
                      dir="ltr"
                      className="text-start"
                      value={startYear}
                      onChange={(event) => setStartYear(event.target.value)}
                    />
                  </div>
                  <div className="space-y-1">
                    <Label htmlFor="loan-month">{tc('month')}</Label>
                    <Input
                      id="loan-month"
                      inputMode="numeric"
                      dir="ltr"
                      className="text-start"
                      value={startMonth}
                      onChange={(event) => setStartMonth(event.target.value)}
                    />
                  </div>
                </div>

                <div className="flex justify-end gap-2">
                  <Button variant="outline" onClick={() => setOpen(false)}>
                    {tc('cancel')}
                  </Button>
                  <Button
                    onClick={() => create.mutate()}
                    disabled={!employee || !total || !installment || create.isPending}
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

      <QueryBoundary isLoading={isLoading} error={error}>
        {loans.length === 0 ? (
          <EmptyState title={t('empty')} />
        ) : (
          <div className="overflow-x-auto rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{tc('employee')}</TableHead>
                  <TableHead className="text-end">{t('total')}</TableHead>
                  <TableHead className="text-end">{t('installment')}</TableHead>
                  <TableHead className="text-end">{t('remaining')}</TableHead>
                  <TableHead>{t('startsOn')}</TableHead>
                  <TableHead>{tc('actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loans.map((loan) => (
                  <TableRow key={loan.id} data-testid="loan-row">
                    <TableCell>
                      <span className="numeric text-muted-foreground">{loan.employee_code}</span>{' '}
                      {loan.employee_name}
                    </TableCell>
                    <TableCell className="numeric text-end">
                      {formatMoney(loan.total, locale)}
                    </TableCell>
                    <TableCell className="numeric text-end">
                      {formatMoney(loan.monthly_installment, locale)}
                    </TableCell>
                    <TableCell className="numeric text-end font-medium">
                      {formatMoney(loan.remaining, locale)}
                    </TableCell>
                    <TableCell>
                      {monthName(loan.start_month, locale)} {loan.start_year}
                    </TableCell>
                    <TableCell>
                      <Badge variant={loan.is_active ? 'secondary' : 'outline'}>
                        {loan.is_active ? t('active') : t('settled')}
                      </Badge>
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
