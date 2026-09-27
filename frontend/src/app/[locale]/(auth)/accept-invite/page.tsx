'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useSearchParams } from 'next/navigation';
import { Suspense } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useHydrated } from '@/hooks/use-hydrated';
import { useRouter } from '@/i18n/navigation';
import { ApiError, api } from '@/lib/api';
import type { SessionUser } from '@/types/api';

function AcceptForm() {
  const t = useTranslations('auth');
  const hydrated = useHydrated();
  const params = useSearchParams();
  const router = useRouter();
  const token = params.get('token') ?? '';

  const schema = z
    .object({
      full_name: z.string().min(2, t('errors.nameRequired')),
      password: z.string().min(10, t('errors.passwordTooShort')),
      confirm: z.string(),
    })
    .refine((values) => values.password === values.confirm, {
      path: ['confirm'],
      message: t('errors.passwordMismatch'),
    });

  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { full_name: '', password: '', confirm: '' },
  });

  const accept = useMutation({
    mutationFn: (values: z.infer<typeof schema>) =>
      api.post<SessionUser>('/api/v1/auth/accept-invite', {
        token,
        full_name: values.full_name,
        password: values.password,
      }),
    onSuccess: () => {
      router.replace('/dashboard');
      router.refresh();
    },
  });

  const serverError = accept.error instanceof ApiError ? accept.error.message : null;

  if (!token) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{t('inviteTitle')}</CardTitle>
          <CardDescription>{t('errors.inviteMissingToken')}</CardDescription>
        </CardHeader>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('inviteTitle')}</CardTitle>
        <CardDescription>{t('inviteHint')}</CardDescription>
      </CardHeader>
      <CardContent>
        <form
          // If a submit ever escapes before React attaches, POST keeps the
          // fields out of the URL, the history and the access log.
          method="post"
          onSubmit={form.handleSubmit((values) => accept.mutate(values))}
          className="space-y-4"
          noValidate
        >
          <div className="space-y-2">
            <Label htmlFor="full_name">{t('fullName')}</Label>
            <Input id="full_name" {...form.register('full_name')} />
            {form.formState.errors.full_name ? (
              <p className="text-sm text-destructive">{form.formState.errors.full_name.message}</p>
            ) : null}
          </div>
          <div className="space-y-2">
            <Label htmlFor="password">{t('newPassword')}</Label>
            <Input
              id="password"
              type="password"
              autoComplete="new-password"
              {...form.register('password')}
            />
            {form.formState.errors.password ? (
              <p className="text-sm text-destructive">{form.formState.errors.password.message}</p>
            ) : null}
          </div>
          <div className="space-y-2">
            <Label htmlFor="confirm">{t('confirmPassword')}</Label>
            <Input
              id="confirm"
              type="password"
              autoComplete="new-password"
              {...form.register('confirm')}
            />
            {form.formState.errors.confirm ? (
              <p className="text-sm text-destructive">{form.formState.errors.confirm.message}</p>
            ) : null}
          </div>
          {serverError ? (
            <p role="alert" className="rounded-md bg-destructive/10 p-2 text-sm text-destructive">
              {serverError}
            </p>
          ) : null}
          <Button
            type="submit"
            className="w-full"
            disabled={!hydrated || accept.isPending}
            aria-busy={!hydrated || accept.isPending}
          >
            {!hydrated || accept.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : null}
            {hydrated ? t('acceptInvite') : t('starting')}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

export default function AcceptInvitePage() {
  return (
    <Suspense fallback={null}>
      <AcceptForm />
    </Suspense>
  );
}
