'use client';

import { Building2, Check, ChevronsUpDown } from 'lucide-react';
import { useLocale, useTranslations } from 'next-intl';

import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useCompany } from '@/providers/company-provider';

export function CompanySwitcher() {
  const t = useTranslations('shell');
  const locale = useLocale();
  const { companyId, memberships, setCompanyId } = useCompany();

  const active = memberships.find((m) => m.company_id === companyId);
  const nameOf = (m: (typeof memberships)[number]) =>
    locale === 'ar' ? m.company_name_ar : m.company_name_en || m.company_name_ar;

  if (memberships.length === 0) return null;

  // One company: show it as a label, not a control that does nothing.
  if (memberships.length === 1) {
    return (
      <div className="flex items-center gap-2 px-2 text-sm font-medium">
        <Building2 className="size-4 shrink-0 text-muted-foreground" aria-hidden />
        <span className="truncate">{active ? nameOf(active) : ''}</span>
      </div>
    );
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" className="w-full justify-between gap-2">
          <span className="flex min-w-0 items-center gap-2">
            <Building2 className="size-4 shrink-0" aria-hidden />
            <span className="truncate">{active ? nameOf(active) : t('selectCompany')}</span>
          </span>
          <ChevronsUpDown className="size-4 shrink-0 opacity-60" aria-hidden />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-56">
        <DropdownMenuLabel>{t('companies')}</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {memberships.map((membership) => (
          <DropdownMenuItem
            key={membership.company_id}
            onSelect={() => setCompanyId(membership.company_id)}
            className="gap-2"
          >
            <Check
              className={
                membership.company_id === companyId ? 'size-4 opacity-100' : 'size-4 opacity-0'
              }
              aria-hidden
            />
            <span className="truncate">{nameOf(membership)}</span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
