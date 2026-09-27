'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useForm } from 'react-hook-form';
import { z } from 'zod';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { useHydrated } from '@/hooks/use-hydrated';
import { Link } from '@/i18n/navigation';
import { api } from '@/lib/api';

export default function ForgotPasswordPage() {
  const t = useTranslations('auth');
  const hydrated = useHydrated();

  const schema = z.object({
    email: z.string().min(1, t('errors.emailRequired')).email(t('errors.emailInvalid')),
  });

  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { email: '' },
  });

  const request = useMutation({
    mutationFn: (values: z.infer<typeof schema>) =>
      api.post<{ detail: string }>('/api/v1/auth/password/reset', values),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t('resetTitle')}</CardTitle>
        <CardDescription>{t('resetHint')}</CardDescription>
      </CardHeader>
      <CardContent>
        {request.isSuccess ? (
          <div className="space-y-4">
            <p className="rounded-md bg-muted p-3 text-sm">{request.data?.detail}</p>
            <Link href="/login" className="text-sm text-primary hover:underline">
              {t('backToSignIn')}
            </Link>
          </div>
        ) : (
          <form
            // If a submit ever escapes before React attaches, POST keeps the
            // fields out of the URL, the history and the access log.
            method="post"
            onSubmit={form.handleSubmit((values) => request.mutate(values))}
            className="space-y-4"
            noValidate
          >
            <div className="space-y-2">
              <Label htmlFor="email">{t('email')}</Label>
              <Input
                id="email"
                type="email"
                dir="ltr"
                className="text-start"
                {...form.register('email')}
              />
              {form.formState.errors.email ? (
                <p className="text-sm text-destructive">{form.formState.errors.email.message}</p>
              ) : null}
            </div>
            <Button
              type="submit"
              className="w-full"
              disabled={!hydrated || request.isPending}
              aria-busy={!hydrated || request.isPending}
            >
              {request.isPending ? <Loader2 className="size-4 animate-spin" aria-hidden /> : null}
              {t('sendResetLink')}
            </Button>
            <Link href="/login" className="block text-sm text-primary hover:underline">
              {t('backToSignIn')}
            </Link>
          </form>
        )}
      </CardContent>
    </Card>
  );
}
