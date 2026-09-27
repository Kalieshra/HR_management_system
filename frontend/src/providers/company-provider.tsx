'use client';

import { useQuery, useQueryClient } from '@tanstack/react-query';
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { useSession } from '@/hooks/use-session';
import { COMPANY_COOKIE, api } from '@/lib/api';
import type { Company, Membership, Paginated } from '@/types/api';

interface CompanyContextValue {
  companyId: number | null;
  membership: Membership | null;
  memberships: Membership[];
  setCompanyId: (id: number) => void;
  isCompanyAdmin: boolean;
  isPlatformAdmin: boolean;
  /** Branch ids a branch_entry user may touch; null means every branch. */
  allowedBranchIds: number[] | null;
}

const CompanyContext = createContext<CompanyContextValue | null>(null);

function readCookie(): number | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${COMPANY_COOKIE}=([^;]*)`));
  const value = match ? Number(decodeURIComponent(match[1])) : NaN;
  return Number.isFinite(value) ? value : null;
}

function writeCookie(id: number) {
  // Readable by JS on purpose: the API client attaches it as a header, and the
  // backend re-checks membership on every request, so it is not a trust anchor.
  document.cookie = `${COMPANY_COOKIE}=${id}; path=/; max-age=${60 * 60 * 24 * 365}; samesite=lax`;
}

export function CompanyProvider({ children }: { children: React.ReactNode }) {
  const { data: session } = useSession();
  const queryClient = useQueryClient();
  const [companyId, setCompanyIdState] = useState<number | null>(null);

  const isPlatformAdmin = Boolean(session?.is_platform_admin);

  // The platform owner is normally a member of nothing, yet the backend grants
  // them every tenant (`core/middleware.py: resolve_company` lets a platform
  // admin through with a `None` membership). Without this they would sign in to
  // an app with no company selected, where every query is disabled.
  const platformCompanies = useQuery({
    queryKey: ['platform', 'companies', 'switcher'],
    queryFn: () => api.get<Paginated<Company>>('/api/v1/platform/companies/?page_size=200'),
    enabled: isPlatformAdmin,
    select: (data) => data.results,
    staleTime: 5 * 60_000,
  });

  const memberships = useMemo(() => {
    const own = session?.memberships ?? [];
    if (!isPlatformAdmin) return own;

    const joined = new Set(own.map((m) => m.company_id));
    const rest = (platformCompanies.data ?? [])
      .filter((company) => company.is_active && !joined.has(company.id))
      .map<Membership>((company) => ({
        // Negative, so it can never collide with a real membership row.
        id: -company.id,
        company_id: company.id,
        company_name_ar: company.name_ar,
        company_name_en: company.name_en,
        company_slug: company.slug,
        role: 'company_admin',
        branches: [],
      }));

    return [...own, ...rest];
  }, [session, isPlatformAdmin, platformCompanies.data]);

  useEffect(() => {
    if (!session) return;
    const stored = readCookie();
    const valid = memberships.some((m) => m.company_id === stored);
    const next = valid ? stored : (memberships[0]?.company_id ?? null);
    if (next !== null) {
      writeCookie(next);
      setCompanyIdState(next);
    } else {
      setCompanyIdState(null);
    }
  }, [session, memberships]);

  const setCompanyId = useCallback(
    (id: number) => {
      writeCookie(id);
      setCompanyIdState(id);
      // Everything cached belongs to the previous tenant.
      queryClient.removeQueries();
    },
    [queryClient],
  );

  const membership = memberships.find((m) => m.company_id === companyId) ?? null;
  const isCompanyAdmin = isPlatformAdmin || membership?.role === 'company_admin';

  const value: CompanyContextValue = {
    companyId,
    membership,
    memberships,
    setCompanyId,
    isCompanyAdmin: Boolean(isCompanyAdmin),
    isPlatformAdmin,
    allowedBranchIds:
      !membership || membership.role === 'company_admin' || isPlatformAdmin
        ? null
        : membership.branches.map((b) => b.id),
  };

  return <CompanyContext.Provider value={value}>{children}</CompanyContext.Provider>;
}

export function useCompany(): CompanyContextValue {
  const context = useContext(CompanyContext);
  if (!context) throw new Error('useCompany must be used inside <CompanyProvider>');
  return context;
}
