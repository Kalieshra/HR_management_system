'use client';

import { useMutation } from '@tanstack/react-query';
import { Download, Loader2, Mail } from 'lucide-react';
import { useLocale, useTranslations } from 'next-intl';
import { toast } from 'sonner';

import { EmptyState } from '@/components/empty-state';
import { PageHeader } from '@/components/page-header';
import { QueryBoundary } from '@/components/query-boundary';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useInvalidateCompany, useReports } from '@/hooks/use-api';
import { ApiError, api } from '@/lib/api';
import { formatDateTime, type Locale } from '@/lib/format';

function formatSize(bytes: number): string {
  if (!bytes) return '—';
  const kb = bytes / 1024;
  return kb < 1024 ? `${Math.round(kb)} KB` : `${(kb / 1024).toFixed(1)} MB`;
}

export default function ReportsPage() {
  const t = useTranslations('reports');
  const tc = useTranslations('common');
  const locale = useLocale() as Locale;
  const invalidate = useInvalidateCompany();

  const { data: reports = [], isLoading, error } = useReports();

  const resend = useMutation({
    mutationFn: (periodId: number) =>
      api.post<{ recipients: string[] }>(`/api/v1/reports/${periodId}/email/`),
    onSuccess: (result) => {
      toast.success(t('sent', { count: result.recipients.length }));
      invalidate();
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : tc('genericError')),
  });

  return (
    <>
      <PageHeader title={t('title')} description={t('subtitle')} />

      <QueryBoundary isLoading={isLoading} error={error}>
        {reports.length === 0 ? (
          <EmptyState title={t('empty')} />
        ) : (
          <div className="overflow-x-auto rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{tc('month')}</TableHead>
                  <TableHead>{t('kind')}</TableHead>
                  <TableHead>{t('generatedAt')}</TableHead>
                  <TableHead>{t('emailedAt')}</TableHead>
                  <TableHead className="text-end">{tc('actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {reports.map((report) => (
                  <TableRow key={report.id} data-testid="report-row">
                    <TableCell>{report.period_label}</TableCell>
                    <TableCell>
                      <Badge variant="secondary" className="uppercase">
                        {report.kind}
                      </Badge>
                      <span className="numeric ms-2 text-xs text-muted-foreground">
                        {formatSize(report.size)}
                      </span>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatDateTime(report.generated_at, locale)}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {report.emailed_at
                        ? formatDateTime(report.emailed_at, locale)
                        : t('notEmailed')}
                    </TableCell>
                    <TableCell>
                      <div className="flex justify-end gap-2">
                        {report.file_url ? (
                          <Button variant="outline" size="sm" asChild>
                            <a href={report.file_url} download>
                              <Download className="size-4" aria-hidden />
                              {tc('download')}
                            </a>
                          </Button>
                        ) : null}
                        {report.kind === 'xlsx' ? (
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => resend.mutate(report.period)}
                            disabled={resend.isPending}
                          >
                            {resend.isPending ? (
                              <Loader2 className="size-4 animate-spin" aria-hidden />
                            ) : (
                              <Mail className="size-4" aria-hidden />
                            )}
                            {t('resend')}
                          </Button>
                        ) : null}
                      </div>
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
