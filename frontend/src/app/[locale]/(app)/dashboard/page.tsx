'use client';

import { AlertTriangle, Info } from 'lucide-react';
import { useLocale, useTranslations } from 'next-intl';
import { useState } from 'react';

import { EmptyState } from '@/components/empty-state';
import { PageHeader } from '@/components/page-header';
import { QueryBoundary } from '@/components/query-boundary';
import { StatCard } from '@/components/stat-card';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { useDashboard } from '@/hooks/use-api';
import { Link } from '@/i18n/navigation';
import { formatMoney, formatPercent, monthName, type Locale } from '@/lib/format';
import { useCompany } from '@/providers/company-provider';

const STATUS_TONE: Record<string, 'secondary' | 'default' | 'outline'> = {
  open: 'outline',
  calculated: 'secondary',
  closed: 'default',
};

export default function DashboardPage() {
  const t = useTranslations('dashboard');
  const tc = useTranslations('common');
  const locale = useLocale() as Locale;
  const { isCompanyAdmin } = useCompany();

  const today = new Date();
  const [year] = useState(today.getFullYear());
  const [month] = useState(today.getMonth() + 1);

  const { data, isLoading, error } = useDashboard(year, month);

  return (
    <>
      <PageHeader
        title={t('title')}
        description={t('subtitle', { month: monthName(month, locale), year })}
        actions={
          data ? (
            <Badge variant={STATUS_TONE[data.status] ?? 'outline'}>
              {tc(`periodStatus.${data.status}`)}
            </Badge>
          ) : null
        }
      />

      <QueryBoundary isLoading={isLoading} error={error}>
        {data ? (
          <div className="space-y-6">
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              <StatCard label={t('employees')} value={String(data.employees)} />
              <StatCard
                label={t('completion')}
                value={`${formatPercent(data.completion, locale)}%`}
                hint={t('completionHint', { recorded: data.recorded, expected: data.expected })}
              />
              <StatCard
                label={t('totalEarnings')}
                value={formatMoney(data.totals?.total_earnings ?? '0', locale)}
                tone="positive"
              />
              <StatCard
                label={t('netSalary')}
                value={formatMoney(data.totals?.net_salary ?? '0', locale)}
              />
            </div>

            {data.alerts.length > 0 ? (
              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">{t('alerts')}</CardTitle>
                </CardHeader>
                <CardContent className="space-y-2">
                  {data.alerts.map((alert) => (
                    <div
                      key={alert.code}
                      className="flex items-center gap-2 rounded-md border p-2 text-sm"
                    >
                      {alert.level === 'warning' ? (
                        <AlertTriangle className="size-4 shrink-0 text-amber-600" aria-hidden />
                      ) : (
                        <Info className="size-4 shrink-0 text-muted-foreground" aria-hidden />
                      )}
                      <span>{t(`alertCodes.${alert.code}`, { count: alert.count })}</span>
                    </div>
                  ))}
                </CardContent>
              </Card>
            ) : null}

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">{t('perBranch')}</CardTitle>
              </CardHeader>
              <CardContent>
                {data.per_branch.length === 0 ? (
                  <EmptyState title={t('noBranches')} />
                ) : (
                  <div className="space-y-3">
                    {data.per_branch.map((branch) => (
                      <div key={branch.branch_id} className="space-y-1">
                        <div className="flex items-center justify-between gap-2 text-sm">
                          <span className="truncate font-medium">{branch.branch}</span>
                          <span className="numeric text-muted-foreground">
                            {formatPercent(branch.completion, locale)}%
                          </span>
                        </div>
                        <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                          <div
                            className="h-full rounded-full bg-primary transition-all"
                            style={{ width: `${Math.min(branch.completion, 100)}%` }}
                          />
                        </div>
                        <p className="text-xs text-muted-foreground">
                          {t('branchHint', {
                            employees: branch.employees,
                            recorded: branch.recorded,
                            expected: branch.expected,
                          })}
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            <div className="flex flex-wrap gap-3 text-sm">
              <Link href="/daily-entry" className="text-primary hover:underline">
                {t('goToDailyEntry')}
              </Link>
              {/* Branch-entry users have no access to payroll, so don't offer it. */}
              {isCompanyAdmin ? (
                <Link href="/payroll" className="text-primary hover:underline">
                  {t('goToPayroll')}
                </Link>
              ) : null}
            </div>
          </div>
        ) : null}
      </QueryBoundary>
    </>
  );
}
