'use client';

import { useTranslations } from 'next-intl';

import { Skeleton } from '@/components/ui/skeleton';
import { ApiError } from '@/lib/api';

/** Renders loading skeletons and a readable error, or the children. */
export function QueryBoundary({
  isLoading,
  error,
  children,
  rows = 5,
}: {
  isLoading: boolean;
  error: unknown;
  children: React.ReactNode;
  rows?: number;
}) {
  const t = useTranslations('common');

  if (isLoading) {
    return (
      <div className="space-y-2">
        {Array.from({ length: rows }).map((_, index) => (
          <Skeleton key={index} className="h-10 w-full" />
        ))}
      </div>
    );
  }

  if (error) {
    const message = error instanceof ApiError ? error.message : t('genericError');
    return (
      <p role="alert" className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
        {message}
      </p>
    );
  }

  return <>{children}</>;
}
