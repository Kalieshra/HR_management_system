'use client';

import { Toaster } from '@/components/ui/sonner';
import { CompanyProvider } from '@/providers/company-provider';
import { QueryProvider } from '@/providers/query-provider';

/**
 * Client-side providers only. `NextIntlClientProvider` stays in the server
 * layout, where it can infer the locale from the request — inside a client
 * component it has no request context and throws.
 */
export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <QueryProvider>
      <CompanyProvider>
        {children}
        <Toaster position="top-center" richColors closeButton />
      </CompanyProvider>
    </QueryProvider>
  );
}
