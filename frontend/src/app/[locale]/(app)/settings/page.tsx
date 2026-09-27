'use client';

import { useMutation, useQuery } from '@tanstack/react-query';
import { Loader2, Plus } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useEffect, useState } from 'react';
import { toast } from 'sonner';

import { PageHeader } from '@/components/page-header';
import { QueryBoundary } from '@/components/query-boundary';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Checkbox } from '@/components/ui/checkbox';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Textarea } from '@/components/ui/textarea';
import { useBranches, useInvalidateCompany, usePolicy } from '@/hooks/use-api';
import { ApiError, api } from '@/lib/api';
import { isoDate } from '@/lib/format';
import { useCompany } from '@/providers/company-provider';
import type { Company, Membership, Paginated, PayrollPolicy, Role } from '@/types/api';

function BranchesTab() {
  const t = useTranslations('settings');
  const tc = useTranslations('common');
  const invalidate = useInvalidateCompany();
  const { data: branches = [], isLoading, error } = useBranches();

  const [nameAr, setNameAr] = useState('');
  const [nameEn, setNameEn] = useState('');
  const [code, setCode] = useState('');

  const create = useMutation({
    mutationFn: () =>
      api.post('/api/v1/branches/', { name_ar: nameAr, name_en: nameEn, code, is_active: true }),
    onSuccess: () => {
      toast.success(tc('saved'));
      invalidate();
      setNameAr('');
      setNameEn('');
      setCode('');
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : tc('genericError')),
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-2">
        <div className="space-y-1">
          <Label htmlFor="branch-ar">{t('branchNameAr')}</Label>
          <Input id="branch-ar" value={nameAr} onChange={(e) => setNameAr(e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label htmlFor="branch-en">{t('branchNameEn')}</Label>
          <Input id="branch-en" value={nameEn} onChange={(e) => setNameEn(e.target.value)} />
        </div>
        <div className="space-y-1">
          <Label htmlFor="branch-code">{t('branchCode')}</Label>
          <Input
            id="branch-code"
            className="w-28"
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
        </div>
        <Button onClick={() => create.mutate()} disabled={!nameAr || create.isPending}>
          {create.isPending ? (
            <Loader2 className="size-4 animate-spin" aria-hidden />
          ) : (
            <Plus className="size-4" aria-hidden />
          )}
          {t('addBranch')}
        </Button>
      </div>

      <QueryBoundary isLoading={isLoading} error={error}>
        <div className="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t('branchNameAr')}</TableHead>
                <TableHead>{t('branchCode')}</TableHead>
                <TableHead className="text-end">{tc('employee')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {branches.map((branch) => (
                <TableRow key={branch.id} data-testid="branch-row">
                  <TableCell>{branch.name_ar}</TableCell>
                  <TableCell className="numeric">{branch.code}</TableCell>
                  <TableCell className="numeric text-end">{branch.employee_count ?? 0}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </QueryBoundary>
    </div>
  );
}

function UsersTab() {
  const t = useTranslations('settings');
  const tc = useTranslations('common');
  const { companyId } = useCompany();
  const invalidate = useInvalidateCompany();

  const [email, setEmail] = useState('');
  const [role, setRole] = useState<Role>('branch_entry');
  const [link, setLink] = useState<string | null>(null);

  const users = useQuery({
    queryKey: ['company', companyId, 'memberships'],
    queryFn: () => api.get<Paginated<Membership>>('/api/v1/users/?page_size=100'),
    enabled: companyId !== null,
    select: (data) => data.results,
  });

  const invite = useMutation({
    mutationFn: () => api.post<{ id: number }>('/api/v1/users/invite/', { email, role }),
    onSuccess: () => {
      toast.success(tc('saved'));
      setEmail('');
      setLink(t('invited'));
      invalidate();
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : tc('genericError')),
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-end gap-2">
        <div className="space-y-1">
          <Label htmlFor="invite-email">{tc('employee')}</Label>
          <Input
            id="invite-email"
            type="email"
            dir="ltr"
            className="w-64 text-start"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="space-y-1">
          <Label htmlFor="invite-role">{t('role')}</Label>
          <Select value={role} onValueChange={(next) => setRole(next as Role)}>
            <SelectTrigger id="invite-role" className="w-48">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="company_admin">{t('roles.company_admin')}</SelectItem>
              <SelectItem value="branch_entry">{t('roles.branch_entry')}</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Button onClick={() => invite.mutate()} disabled={!email || invite.isPending}>
          {invite.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
          {t('inviteUser')}
        </Button>
      </div>

      {link ? <p className="rounded-md bg-muted p-2 text-sm">{link}</p> : null}

      <QueryBoundary isLoading={users.isLoading} error={users.error}>
        <div className="overflow-x-auto rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{tc('employee')}</TableHead>
                <TableHead>{t('role')}</TableHead>
                <TableHead>{tc('branch')}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(users.data ?? []).map((membership) => (
                <TableRow key={membership.id} data-testid="user-row">
                  <TableCell>{membership.company_name_ar}</TableCell>
                  <TableCell>
                    <Badge variant="secondary">{t(`roles.${membership.role}`)}</Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {membership.branches.map((b) => b.name_ar).join('، ') || tc('all')}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </QueryBoundary>
    </div>
  );
}

function PolicyTab() {
  const t = useTranslations('settings.policy');
  const tc = useTranslations('common');
  const invalidate = useInvalidateCompany();
  const { data, isLoading, error } = usePolicy();

  const [form, setForm] = useState<PayrollPolicy | null>(null);
  useEffect(() => {
    if (data) setForm({ ...data, effective_from: isoDate(new Date()) });
  }, [data]);

  const save = useMutation({
    mutationFn: (values: PayrollPolicy) => api.post('/api/v1/policy/', values),
    onSuccess: () => {
      toast.success(t('saved'));
      invalidate();
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : tc('genericError')),
  });

  const field = (key: keyof PayrollPolicy, label: string, props: Record<string, unknown> = {}) => (
    <div className="space-y-1">
      <Label htmlFor={String(key)}>{label}</Label>
      <Input
        id={String(key)}
        dir="ltr"
        className="text-start"
        value={String(form?.[key] ?? '')}
        onChange={(event) =>
          setForm((current) => (current ? { ...current, [key]: event.target.value } : current))
        }
        {...props}
      />
    </div>
  );

  return (
    <QueryBoundary isLoading={isLoading} error={error}>
      {form ? (
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {field('effective_from', t('effectiveFrom'), { type: 'date' })}
            {field('month_day_basis', t('monthDayBasis'), { inputMode: 'numeric' })}
            {field('overtime_multiplier', t('overtimeMultiplier'), { inputMode: 'decimal' })}
            {field('absence_multiplier', t('absenceMultiplier'), { inputMode: 'decimal' })}
            {field('sick_deduction_rate', t('sickRate'), { inputMode: 'decimal' })}
            {field('insurance_employee_rate', t('insuranceRate'), { inputMode: 'decimal' })}
            {field('default_daily_hours', t('defaultDailyHours'), { inputMode: 'decimal' })}

            <div className="space-y-1">
              <Label htmlFor="fingerprint-base">{t('fingerprintBase')}</Label>
              <Select
                value={form.fingerprint_penalty_base}
                onValueChange={(next) =>
                  setForm({ ...form, fingerprint_penalty_base: next as 'earned' | 'base' })
                }
              >
                <SelectTrigger id="fingerprint-base">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="earned">{t('fingerprintOptions.earned')}</SelectItem>
                  <SelectItem value="base">{t('fingerprintOptions.base')}</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <p className="text-sm text-muted-foreground">{t('monthDayBasisHint')}</p>

          <div className="flex items-start gap-2">
            <Checkbox
              id="income-tax"
              checked={form.income_tax_enabled}
              onCheckedChange={(checked) =>
                setForm({ ...form, income_tax_enabled: checked === true })
              }
            />
            <div className="space-y-1">
              <Label htmlFor="income-tax">{t('incomeTax')}</Label>
              <p className="text-xs text-muted-foreground">{t('incomeTaxHint')}</p>
            </div>
          </div>

          <Button onClick={() => save.mutate(form)} disabled={save.isPending}>
            {save.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
            {t('newVersion')}
          </Button>
        </div>
      ) : null}
    </QueryBoundary>
  );
}

function CompanyTab() {
  const t = useTranslations('settings');
  const tc = useTranslations('common');
  const { companyId } = useCompany();
  const invalidate = useInvalidateCompany();

  const company = useQuery({
    queryKey: ['company', companyId, 'settings'],
    queryFn: () => api.get<Company>('/api/v1/company'),
    enabled: companyId !== null,
  });

  const [emails, setEmails] = useState('');
  const [reportDay, setReportDay] = useState('1');
  const [language, setLanguage] = useState<'ar' | 'en'>('ar');

  // Seed the form once the company loads; later edits belong to the user.
  useEffect(() => {
    if (!company.data) return;
    setEmails((company.data.report_emails ?? []).join('\n'));
    setReportDay(String(company.data.report_day ?? 1));
    setLanguage(company.data.report_language ?? 'ar');
  }, [company.data]);

  const save = useMutation({
    mutationFn: () =>
      api.patch<Company>('/api/v1/company', {
        report_emails: emails
          .split('\n')
          .map((line) => line.trim())
          .filter(Boolean),
        report_day: Number(reportDay),
        report_language: language,
      }),
    onSuccess: () => {
      toast.success(tc('saved'));
      invalidate();
    },
    onError: (err) => toast.error(err instanceof ApiError ? err.message : tc('genericError')),
  });

  return (
    <QueryBoundary isLoading={company.isLoading} error={company.error}>
      <Card className="max-w-xl">
        <CardHeader className="pb-2">
          <CardTitle className="text-base">{company.data?.name_ar}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1">
            <Label htmlFor="report-emails">{t('reportEmails')}</Label>
            <Textarea
              id="report-emails"
              rows={4}
              dir="ltr"
              className="text-start"
              value={emails}
              onChange={(event) => setEmails(event.target.value)}
            />
            <p className="text-xs text-muted-foreground">{t('reportEmailsHint')}</p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1">
              <Label htmlFor="report-day">{t('reportDay')}</Label>
              <Input
                id="report-day"
                inputMode="numeric"
                dir="ltr"
                className="text-start"
                value={reportDay}
                onChange={(event) => setReportDay(event.target.value)}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="report-language">{t('reportLanguage')}</Label>
              <Select value={language} onValueChange={(next) => setLanguage(next as 'ar' | 'en')}>
                <SelectTrigger id="report-language">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="ar">العربية</SelectItem>
                  <SelectItem value="en">English</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <Button onClick={() => save.mutate()} disabled={save.isPending}>
            {save.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
            {tc('save')}
          </Button>
        </CardContent>
      </Card>
    </QueryBoundary>
  );
}

export default function SettingsPage() {
  const t = useTranslations('settings');

  return (
    <>
      <PageHeader title={t('title')} description={t('subtitle')} />

      <Tabs defaultValue="branches">
        <TabsList>
          <TabsTrigger value="branches">{t('tabs.branches')}</TabsTrigger>
          <TabsTrigger value="users">{t('tabs.users')}</TabsTrigger>
          <TabsTrigger value="policy">{t('tabs.policy')}</TabsTrigger>
          <TabsTrigger value="company">{t('tabs.company')}</TabsTrigger>
        </TabsList>

        <TabsContent value="branches" className="mt-4">
          <BranchesTab />
        </TabsContent>
        <TabsContent value="users" className="mt-4">
          <UsersTab />
        </TabsContent>
        <TabsContent value="policy" className="mt-4">
          <PolicyTab />
        </TabsContent>
        <TabsContent value="company" className="mt-4">
          <CompanyTab />
        </TabsContent>
      </Tabs>
    </>
  );
}
