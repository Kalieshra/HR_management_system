'use client';

import { useMutation, useQuery } from '@tanstack/react-query';
import { Loader2, Plus, Power, UserPlus } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useState } from 'react';
import { toast } from 'sonner';

import { EmptyState } from '@/components/empty-state';
import { PageHeader } from '@/components/page-header';
import { QueryBoundary } from '@/components/query-boundary';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { ApiError, api } from '@/lib/api';
import { useQueryClient } from '@tanstack/react-query';
import type { Company, Paginated } from '@/types/api';

export default function PlatformCompaniesPage() {
  const t = useTranslations('platform');
  const tc = useTranslations('common');
  const te = useTranslations('employees');
  const queryClient = useQueryClient();

  const companies = useQuery({
    queryKey: ['platform', 'companies'],
    queryFn: () => api.get<Paginated<Company>>('/api/v1/platform/companies/?page_size=200'),
    select: (data) => data.results,
  });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['platform'] });
  const onError = (err: unknown) =>
    toast.error(err instanceof ApiError ? err.message : tc('genericError'));

  const [open, setOpen] = useState(false);
  const [nameAr, setNameAr] = useState('');
  const [nameEn, setNameEn] = useState('');
  const [slug, setSlug] = useState('');

  const [inviteFor, setInviteFor] = useState<Company | null>(null);
  const [inviteEmail, setInviteEmail] = useState('');

  const create = useMutation({
    mutationFn: () =>
      api.post('/api/v1/platform/companies/', {
        name_ar: nameAr,
        name_en: nameEn,
        slug,
        report_emails: [],
        report_day: 1,
      }),
    onSuccess: () => {
      toast.success(tc('saved'));
      refresh();
      setOpen(false);
      setNameAr('');
      setNameEn('');
      setSlug('');
    },
    onError,
  });

  const toggle = useMutation({
    mutationFn: (company: Company) =>
      api.post(
        `/api/v1/platform/companies/${company.id}/${company.is_active ? 'suspend' : 'activate'}/`,
      ),
    onSuccess: () => {
      toast.success(tc('saved'));
      refresh();
    },
    onError,
  });

  const invite = useMutation({
    mutationFn: () =>
      api.post(`/api/v1/platform/companies/${inviteFor?.id}/invite-admin/`, {
        email: inviteEmail,
        role: 'company_admin',
      }),
    onSuccess: () => {
      toast.success(tc('saved'));
      setInviteFor(null);
      setInviteEmail('');
      refresh();
    },
    onError,
  });

  return (
    <>
      <PageHeader
        title={t('companies')}
        description={t('subtitle')}
        actions={
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="size-4" aria-hidden />
                {t('addCompany')}
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{t('addCompany')}</DialogTitle>
              </DialogHeader>
              <div className="space-y-4">
                <div className="space-y-1">
                  <Label htmlFor="company-ar">{te('nameAr')}</Label>
                  <Input
                    id="company-ar"
                    value={nameAr}
                    onChange={(e) => setNameAr(e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="company-en">{te('nameEn')}</Label>
                  <Input
                    id="company-en"
                    dir="ltr"
                    className="text-start"
                    value={nameEn}
                    onChange={(e) => {
                      setNameEn(e.target.value);
                      if (!slug) {
                        setSlug(e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, '-'));
                      }
                    }}
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="company-slug">slug</Label>
                  <Input
                    id="company-slug"
                    dir="ltr"
                    className="text-start"
                    value={slug}
                    onChange={(e) => setSlug(e.target.value)}
                  />
                </div>
                <div className="flex justify-end gap-2">
                  <Button variant="outline" onClick={() => setOpen(false)}>
                    {tc('cancel')}
                  </Button>
                  <Button
                    onClick={() => create.mutate()}
                    disabled={!nameAr || !slug || create.isPending}
                  >
                    {create.isPending ? (
                      <Loader2 className="size-4 animate-spin" aria-hidden />
                    ) : null}
                    {tc('save')}
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        }
      />

      <QueryBoundary isLoading={companies.isLoading} error={companies.error}>
        {(companies.data ?? []).length === 0 ? (
          <EmptyState title={t('empty')} />
        ) : (
          <div className="overflow-x-auto rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{te('nameAr')}</TableHead>
                  <TableHead>slug</TableHead>
                  <TableHead className="text-end">{t('employeesTotal')}</TableHead>
                  <TableHead>{te('active')}</TableHead>
                  <TableHead className="text-end">{tc('actions')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(companies.data ?? []).map((company) => (
                  <TableRow key={company.id} data-testid="company-row">
                    <TableCell>{company.name_ar}</TableCell>
                    <TableCell className="numeric text-muted-foreground">{company.slug}</TableCell>
                    <TableCell className="numeric text-end">
                      {company.employee_count ?? 0}
                    </TableCell>
                    <TableCell>
                      <Badge variant={company.is_active ? 'secondary' : 'outline'}>
                        {company.is_active ? te('active') : te('inactive')}
                      </Badge>
                    </TableCell>
                    <TableCell>
                      <div className="flex justify-end gap-2">
                        <Button variant="outline" size="sm" onClick={() => setInviteFor(company)}>
                          <UserPlus className="size-4" aria-hidden />
                          {t('inviteAdmin')}
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => toggle.mutate(company)}
                          disabled={toggle.isPending}
                        >
                          <Power className="size-4" aria-hidden />
                          {company.is_active ? t('suspend') : t('activate')}
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </QueryBoundary>

      <Dialog open={inviteFor !== null} onOpenChange={(next) => !next && setInviteFor(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {t('inviteAdmin')} — {inviteFor?.name_ar}
            </DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-1">
              <Label htmlFor="invite-admin-email">{tc('employee')}</Label>
              <Input
                id="invite-admin-email"
                type="email"
                dir="ltr"
                className="text-start"
                value={inviteEmail}
                onChange={(event) => setInviteEmail(event.target.value)}
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => setInviteFor(null)}>
                {tc('cancel')}
              </Button>
              <Button onClick={() => invite.mutate()} disabled={!inviteEmail || invite.isPending}>
                {invite.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
                {tc('save')}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
