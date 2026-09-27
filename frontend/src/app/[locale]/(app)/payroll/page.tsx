'use client';

import { useTranslations } from 'next-intl';
import { useEffect } from 'react';

import { EmptyState } from '@/components/empty-state';
import { PageHeader } from '@/components/page-header';
import { QueryBoundary } from '@/components/query-boundary';
import { usePeriods } from '@/hooks/use-api';
import { useRouter } from '@/i18n/navigation';

/** Sends the user straight to the newest month's review grid. */
export default function PayrollIndexPage() {
  const t = useTranslations('payroll');
  const router = useRouter();
  const { data: periods, isLoading, error } = usePeriods();

  const newest = periods?.[0];

  useEffect(() => {
    if (newest) router.replace(`/payroll/${newest.year}/${newest.month}`);
  }, [newest, router]);

  return (
    <>
      <PageHeader title={t('title')} />
      <QueryBoundary isLoading={isLoading} error={error}>
        {!newest ? <EmptyState title={t('noLines')} description={t('noLinesHint')} /> : null}
      </QueryBoundary>
    </>
  );
}
