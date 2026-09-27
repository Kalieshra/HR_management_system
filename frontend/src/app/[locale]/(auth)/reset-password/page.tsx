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
import { Link, useRouter } from '@/i18n/navigation';
import { ApiError, api } from '@/lib/api';

function ResetForm() {
  const t = useTranslations('auth');
  const hydrated = useHydrated();
  const params = useSearchParams();
  const router = useRouter();

  const schema = z
    .object({
      new_password: z.string().min(10, t('errors.passwordTooShort')),
      confirm: z.string(),
    })
    .refine((values) => values.new_password === values.confirm, {
      path: ['confirm'],
      message: t('errors.passwordMismatch'),
    });

  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { new_password: '', confirm: '' },
  });

  const reset = useMutation({
    mutationFn: (values: z.infer<typeof schema>) =>
      api.post('/api/v1/auth/password/reset/confirm', {
        uid: params.get('uid') ?? '',
        token: params.get('token') ?? '',
        new_password: values.new_password,
      }),
    onSuccess: () => router.replace('/login'),
  });

  const serverError = reset.error instanceof ApiError ? reset.error.message : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('chooseNewPassword')}</CardTitle>
        <CardDescription>{t('chooseNewPasswordHint')}</CardDescription>
      </CardHeader>
      <CardContent>
        <form
          // If a submit ever escapes before React attaches, POST keeps the
          // fields out of the URL, the history and the access log.
          method="post"
          onSubmit={form.handleSubmit((values) => reset.mutate(values))}
          className="space-y-4"
          noValidate
        >
          <div className="space-y-2">
            <Label htmlFor="new_password">{t('newPassword')}</Label>
            <Input
              id="new_password"
              type="password"
              autoComplete="new-password"
              {...form.register('new_password')}
            />
            {form.formState.errors.new_password ? (
              <p className="text-sm text-destructive">
                {form.formState.errors.new_password.message}
              </p>
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
            disabled={!hydrated || reset.isPending}
            aria-busy={!hydrated || reset.isPending}
          >
            {!hydrated || reset.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : null}
            {hydrated ? t('savePassword') : t('starting')}
          </Button>
          <Link href="/login" className="block text-sm text-primary hover:underline">
            {t('backToSignIn')}
          </Link>
        </form>
      </CardContent>
    </Card>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetForm />
    </Suspense>
  );
}
