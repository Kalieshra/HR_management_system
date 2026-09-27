'use client';

import { LogOut, User as UserIcon } from 'lucide-react';
import { useTranslations } from 'next-intl';

import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { useLogout, useSession } from '@/hooks/use-session';
import { useRouter } from '@/i18n/navigation';

export function UserMenu() {
  const t = useTranslations('shell');
  const { data: session } = useSession();
  const logout = useLogout();
  const router = useRouter();

  if (!session) return null;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="ghost" size="sm" className="gap-2">
          <UserIcon className="size-4" aria-hidden />
          <span className="hidden max-w-[12rem] truncate sm:inline">
            {session.full_name || session.email}
          </span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel className="truncate font-normal text-muted-foreground">
          {session.email}
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          className="gap-2"
          onSelect={() =>
            logout.mutate(undefined, {
              onSuccess: () => router.replace('/login'),
            })
          }
        >
          <LogOut className="size-4 rtl:rotate-180" aria-hidden />
          {t('signOut')}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
