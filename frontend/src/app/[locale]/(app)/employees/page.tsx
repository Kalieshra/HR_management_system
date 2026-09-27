'use client';

import { Pencil, Plus, Upload } from 'lucide-react';
import { useLocale, useTranslations } from 'next-intl';
import { useMemo, useState } from 'react';

import { EmptyState } from '@/components/empty-state';
import { PageHeader } from '@/components/page-header';
import { QueryBoundary } from '@/components/query-boundary';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useBranches, useEmployees } from '@/hooks/use-api';
import { formatMoney, formatQuantity, type Locale } from '@/lib/format';
import { useCompany } from '@/providers/company-provider';
import type { Employee } from '@/types/api';

import { EmployeeForm } from './employee-form';
import { ImportDialog } from './import-dialog';

const ALL = 'all';

export default function EmployeesPage() {
  const t = useTranslations('employees');
  const tc = useTranslations('common');
  const locale = useLocale() as Locale;
  const { isCompanyAdmin } = useCompany();

  const [search, setSearch] = useState('');
  const [branch, setBranch] = useState<string>(ALL);
  const [editing, setEditing] = useState<Employee | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);

  const { data: branches = [] } = useBranches();
  const { data: employees, isLoading, error } = useEmployees();

  const filtered = useMemo(() => {
    const term = search.trim().toLowerCase();
    return (employees ?? []).filter((employee) => {
      if (branch !== ALL && String(employee.branch) !== branch) return false;
      if (!term) return true;
      return [employee.code, employee.name_ar, employee.name_en, employee.job_title]
        .filter(Boolean)
        .some((value) => value.toLowerCase().includes(term));
    });
  }, [employees, search, branch]);

  return (
    <>
      <PageHeader
        title={t('title')}
        description={t('subtitle')}
        actions={
          isCompanyAdmin ? (
            <>
              <Button variant="outline" onClick={() => setImportOpen(true)}>
                <Upload className="size-4" aria-hidden />
                {t('import.title')}
              </Button>
              <Button
                onClick={() => {
                  setEditing(null);
                  setFormOpen(true);
                }}
              >
                <Plus className="size-4" aria-hidden />
                {t('add')}
              </Button>
            </>
          ) : null
        }
      />

      <div className="mb-4 flex flex-wrap gap-2">
        <Input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder={t('searchPlaceholder')}
          className="max-w-xs"
          aria-label={tc('search')}
        />
        <Select value={branch} onValueChange={setBranch}>
          <SelectTrigger className="max-w-[14rem]" aria-label={tc('branch')}>
            <SelectValue placeholder={tc('branch')} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>{tc('all')}</SelectItem>
            {branches.map((item) => (
              <SelectItem key={item.id} value={String(item.id)}>
                {item.name_ar}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <QueryBoundary isLoading={isLoading} error={error}>
        {filtered.length === 0 ? (
          <EmptyState title={t('empty')} description={t('emptyHint')} />
        ) : (
          <div className="overflow-x-auto rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('code')}</TableHead>
                  <TableHead>{t('nameAr')}</TableHead>
                  <TableHead>{tc('branch')}</TableHead>
                  <TableHead>{t('jobTitle')}</TableHead>
                  <TableHead className="text-end">{t('dailyHours')}</TableHead>
                  <TableHead className="text-end">{t('baseSalary')}</TableHead>
                  <TableHead className="text-end">{t('insurableSalary')}</TableHead>
                  <TableHead>{t('active')}</TableHead>
                  {isCompanyAdmin ? <TableHead className="w-10" /> : null}
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((employee) => (
                  <TableRow key={employee.id} data-testid="employee-row">
                    <TableCell className="numeric font-medium">{employee.code}</TableCell>
                    <TableCell>{employee.name_ar}</TableCell>
                    <TableCell className="text-muted-foreground">{employee.branch_name}</TableCell>
                    <TableCell className="text-muted-foreground">{employee.job_title}</TableCell>
                    <TableCell className="numeric text-end">
                      {formatQuantity(employee.daily_hours, locale)}
                    </TableCell>
                    <TableCell className="numeric text-end">
                      {formatMoney(employee.base_salary, locale)}
                    </TableCell>
                    <TableCell className="numeric text-end">
                      {formatMoney(employee.insurable_salary, locale)}
                    </TableCell>
                    <TableCell>
                      <Badge variant={employee.is_active ? 'secondary' : 'outline'}>
                        {employee.is_active ? t('active') : t('inactive')}
                      </Badge>
                    </TableCell>
                    {isCompanyAdmin ? (
                      <TableCell>
                        <Button
                          variant="ghost"
                          size="icon"
                          aria-label={t('edit')}
                          onClick={() => {
                            setEditing(employee);
                            setFormOpen(true);
                          }}
                        >
                          <Pencil className="size-4" aria-hidden />
                        </Button>
                      </TableCell>
                    ) : null}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </QueryBoundary>

      <EmployeeForm open={formOpen} onOpenChange={setFormOpen} employee={editing} />
      <ImportDialog open={importOpen} onOpenChange={setImportOpen} />
    </>
  );
}
