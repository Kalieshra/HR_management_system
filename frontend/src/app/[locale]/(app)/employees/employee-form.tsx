'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { toast } from 'sonner';
import { z } from 'zod';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useBranches, useInvalidateCompany } from '@/hooks/use-api';
import { ApiError, api } from '@/lib/api';
import type { Employee } from '@/types/api';

export function EmployeeForm({
  open,
  onOpenChange,
  employee,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  employee: Employee | null;
}) {
  const t = useTranslations('employees');
  const tc = useTranslations('common');
  const { data: branches = [] } = useBranches();
  const invalidate = useInvalidateCompany();

  const schema = z.object({
    code: z.string().min(1, tc('required')),
    name_ar: z.string().min(1, tc('required')),
    name_en: z.string().optional(),
    branch: z.coerce.number().int().positive(tc('required')),
    job_title: z.string().optional(),
    national_id: z.string().optional(),
    daily_hours: z.string().min(1, tc('required')),
    base_salary: z.string().min(1, tc('required')),
    insurable_salary: z.string().optional(),
    is_active: z.boolean(),
  });

  type Values = z.input<typeof schema>;

  const form = useForm<Values>({
    resolver: zodResolver(schema),
    defaultValues: {
      code: '',
      name_ar: '',
      name_en: '',
      branch: undefined,
      job_title: '',
      national_id: '',
      daily_hours: '9',
      base_salary: '0',
      insurable_salary: '0',
      is_active: true,
    },
  });

  useEffect(() => {
    if (!open) return;
    form.reset(
      employee
        ? {
            code: employee.code,
            name_ar: employee.name_ar,
            name_en: employee.name_en,
            branch: employee.branch,
            job_title: employee.job_title,
            national_id: employee.national_id,
            daily_hours: employee.daily_hours,
            base_salary: employee.base_salary,
            insurable_salary: employee.insurable_salary,
            is_active: employee.is_active,
          }
        : {
            code: '',
            name_ar: '',
            name_en: '',
            branch: branches[0]?.id,
            job_title: '',
            national_id: '',
            daily_hours: '9',
            base_salary: '0',
            insurable_salary: '0',
            is_active: true,
          },
    );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, employee, branches.length]);

  const save = useMutation({
    mutationFn: (values: Values) =>
      employee
        ? api.patch<Employee>(`/api/v1/employees/${employee.id}/`, values)
        : api.post<Employee>('/api/v1/employees/', values),
    onSuccess: () => {
      toast.success(tc('saved'));
      invalidate();
      onOpenChange(false);
    },
    onError: (error) => {
      if (error instanceof ApiError) {
        for (const [field, messages] of Object.entries(error.fields)) {
          form.setError(field as keyof Values, { message: messages[0] });
        }
        if (Object.keys(error.fields).length === 0) toast.error(error.message);
      } else {
        toast.error(tc('genericError'));
      }
    },
  });

  const field = (name: keyof Values, label: string, props: Record<string, unknown> = {}) => (
    <div className="space-y-2">
      <Label htmlFor={name}>{label}</Label>
      <Input id={name} {...props} {...form.register(name)} />
      {form.formState.errors[name] ? (
        <p className="text-sm text-destructive">
          {String(form.formState.errors[name]?.message ?? '')}
        </p>
      ) : null}
    </div>
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>{employee ? t('edit') : t('add')}</DialogTitle>
          <DialogDescription>{t('subtitle')}</DialogDescription>
        </DialogHeader>

        <form
          onSubmit={form.handleSubmit((values) => save.mutate(values))}
          className="grid gap-4 sm:grid-cols-2"
          noValidate
        >
          {field('code', t('code'))}
          {field('name_ar', t('nameAr'))}
          {field('name_en', t('nameEn'))}

          <div className="space-y-2">
            <Label htmlFor="branch">{tc('branch')}</Label>
            <Select
              value={String(form.watch('branch') ?? '')}
              onValueChange={(value) => form.setValue('branch', Number(value))}
            >
              <SelectTrigger id="branch">
                <SelectValue placeholder={tc('branch')} />
              </SelectTrigger>
              <SelectContent>
                {branches.map((branch) => (
                  <SelectItem key={branch.id} value={String(branch.id)}>
                    {branch.name_ar}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {form.formState.errors.branch ? (
              <p className="text-sm text-destructive">{form.formState.errors.branch.message}</p>
            ) : null}
          </div>

          {field('job_title', t('jobTitle'))}
          {field('national_id', t('nationalId'), { dir: 'ltr', className: 'text-start' })}
          {field('daily_hours', t('dailyHours'), {
            inputMode: 'decimal',
            dir: 'ltr',
            className: 'text-start',
          })}
          {field('base_salary', t('baseSalary'), {
            inputMode: 'decimal',
            dir: 'ltr',
            className: 'text-start',
          })}
          {field('insurable_salary', t('insurableSalary'), {
            inputMode: 'decimal',
            dir: 'ltr',
            className: 'text-start',
          })}

          <div className="flex items-center justify-end gap-2 sm:col-span-2">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              {tc('cancel')}
            </Button>
            <Button type="submit" disabled={save.isPending}>
              {save.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
              {tc('save')}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
