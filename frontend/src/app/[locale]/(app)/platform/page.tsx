'use client';

import { useQuery } from '@tanstack/react-query';
import { useLocale, useTranslations } from 'next-intl';

import { PageHeader } from '@/components/page-header';
import { QueryBoundary } from '@/components/query-boundary';
import { StatCard } from '@/components/stat-card';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Link } from '@/i18n/navigation';
import { api } from '@/lib/api';
import { formatDateTime, type Locale } from '@/lib/format';

interface PlatformStats {
  companies_total: number;
  companies_active: number;
  users_total: number;
  employees_total: number;
  periods_closed: number;
  reports_sent: number;
  recent_reports: Array<{
    id: number;
    company__name_ar: string;
    kind: string;
    emailed_at: string;
  }>;
}

export default function PlatformPage() {
  const t = useTranslations('platform');
  const locale = useLocale() as Locale;

  const stats = useQuery({
    queryKey: ['platform', 'stats'],
    queryFn: () => api.get<PlatformStats[]>('/api/v1/platform/stats/'),
    select: (data) => (Array.isArray(data) ? data[0] : (data as unknown as PlatformStats)),
  });

  return (
    <>
      <PageHeader title={t('title')} description={t('subtitle')} />

      <QueryBoundary isLoading={stats.isLoading} error={stats.error}>
        {stats.data ? (
          <div className="space-y-6">
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              <StatCard label={t('companiesTotal')} value={String(stats.data.companies_total)} />
              <StatCard
                label={t('companiesActive')}
                value={String(stats.data.companies_active)}
                tone="positive"
              />
              <StatCard label={t('usersTotal')} value={String(stats.data.users_total)} />
              <StatCard label={t('employeesTotal')} value={String(stats.data.employees_total)} />
              <StatCard label={t('periodsClosed')} value={String(stats.data.periods_closed)} />
              <StatCard label={t('reportsSent')} value={String(stats.data.reports_sent)} />
            </div>

            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">{t('recentReports')}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {stats.data.recent_reports.length === 0 ? (
                  <p className="text-sm text-muted-foreground">{t('empty')}</p>
                ) : (
                  stats.data.recent_reports.map((report) => (
                    <div
                      key={report.id}
                      className="flex items-center justify-between gap-3 rounded-md border p-2 text-sm"
                    >
                      <span className="truncate">{report.company__name_ar}</span>
                      <span className="text-muted-foreground">
                        {formatDateTime(report.emailed_at, locale)}
                      </span>
                    </div>
                  ))
                )}
              </CardContent>
            </Card>

            <Link href="/platform/companies" className="text-sm text-primary hover:underline">
              {t('companies')}
            </Link>
          </div>
        ) : null}
      </QueryBoundary>
    </>
  );
}
