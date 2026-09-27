'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { Loader2 } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useSearchParams } from 'next/navigation';
import { Suspense } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { LanguageSwitcher } from '@/components/language-switcher';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useHydrated } from '@/hooks/use-hydrated';
import { useLogin } from '@/hooks/use-session';
import { Link, useRouter } from '@/i18n/navigation';
import { ApiError } from '@/lib/api';

function LoginForm() {
  const t = useTranslations('auth');
  const hydrated = useHydrated();
  const router = useRouter();
  const params = useSearchParams();
  const login = useLogin();

  const schema = z.object({
    email: z.string().min(1, t('errors.emailRequired')).email(t('errors.emailInvalid')),
    password: z.string().min(1, t('errors.passwordRequired')),
  });

  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { email: '', password: '' },
  });

  const onSubmit = form.handleSubmit((values) => {
    login.mutate(values, {
      onSuccess: () => {
        const next = params.get('next');
        router.replace(next && next.startsWith('/') ? next : '/dashboard');
        router.refresh();
      },
    });
  });

  const serverError =
    login.error instanceof ApiError
      ? login.error.message
      : login.error
        ? t('errors.generic')
        : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('signIn')}</CardTitle>
        <CardDescription>{t('signInHint')}</CardDescription>
      </CardHeader>
      <CardContent>
        <form
          // If a submit ever escapes before React attaches, POST keeps the
          // fields out of the URL, the history and the access log.
          method="post"
          onSubmit={onSubmit}
          className="space-y-4"
          noValidate
        >
          <div className="space-y-2">
            <Label htmlFor="email">{t('email')}</Label>
            <Input
              id="email"
              type="email"
              autoComplete="email"
              dir="ltr"
              className="text-start"
              aria-invalid={Boolean(form.formState.errors.email)}
              {...form.register('email')}
            />
            {form.formState.errors.email ? (
              <p className="text-sm text-destructive">{form.formState.errors.email.message}</p>
            ) : null}
          </div>

          <div className="space-y-2">
            <Label htmlFor="password">{t('password')}</Label>
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              aria-invalid={Boolean(form.formState.errors.password)}
              {...form.register('password')}
            />
            {form.formState.errors.password ? (
              <p className="text-sm text-destructive">{form.formState.errors.password.message}</p>
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
            disabled={!hydrated || login.isPending}
            aria-busy={!hydrated || login.isPending}
          >
            {!hydrated || login.isPending ? (
              <Loader2 className="size-4 animate-spin" aria-hidden />
            ) : null}
            {hydrated ? t('signIn') : t('starting')}
          </Button>

          <div className="flex items-center justify-between">
            <Link href="/forgot-password" className="text-sm text-primary hover:underline">
              {t('forgotPassword')}
            </Link>
            <LanguageSwitcher />
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={null}>
      <LoginForm />
    </Suspense>
  );
}
