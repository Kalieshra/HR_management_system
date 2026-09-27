'use client';

import { useLocale, useTranslations } from 'next-intl';

import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { monthName, type Locale } from '@/lib/format';
import type { Period } from '@/types/api';

export function PeriodSelect({
  periods,
  value,
  onChange,
  label,
}: {
  periods: Period[];
  value: number | null;
  onChange: (id: number) => void;
  label?: string;
}) {
  const t = useTranslations('payroll');
  const locale = useLocale() as Locale;

  return (
    <div className="space-y-1">
      <Label htmlFor="period-select">{label ?? t('selectPeriod')}</Label>
      <Select
        value={value === null ? '' : String(value)}
        onValueChange={(next) => onChange(Number(next))}
      >
        <SelectTrigger id="period-select" className="w-52">
          <SelectValue placeholder={t('selectPeriod')} />
        </SelectTrigger>
        <SelectContent>
          {periods.map((period) => (
            <SelectItem key={period.id} value={String(period.id)}>
              {monthName(period.month, locale)} {period.year}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
