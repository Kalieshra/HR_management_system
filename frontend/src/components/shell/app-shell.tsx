'use client';

import { Menu } from 'lucide-react';
import { useTranslations } from 'next-intl';
import { useState } from 'react';

import { LanguageSwitcher } from '@/components/language-switcher';
import { CompanySwitcher } from '@/components/shell/company-switcher';
import { COMPANY_NAV, PLATFORM_NAV, type NavItem } from '@/components/shell/nav-items';
import { UserMenu } from '@/components/shell/user-menu';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from '@/components/ui/sheet';
import { Link, usePathname } from '@/i18n/navigation';
import { cn } from '@/lib/utils';
import { useCompany } from '@/providers/company-provider';

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const t = useTranslations('nav');
  const pathname = usePathname();
  const { isCompanyAdmin, isPlatformAdmin } = useCompany();

  const visible = (item: NavItem) => {
    if (item.platformOnly) return isPlatformAdmin;
    if (item.adminOnly) return isCompanyAdmin;
    return true;
  };

  const render = (items: NavItem[]) =>
    items.filter(visible).map((item) => {
      const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
      const Icon = item.icon;
      return (
        <Link
          key={item.href}
          href={item.href}
          onClick={onNavigate}
          aria-current={active ? 'page' : undefined}
          className={cn(
            'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
            active
              ? 'bg-primary text-primary-foreground'
              : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
          )}
        >
          <Icon className="size-4 shrink-0" aria-hidden />
          <span className="truncate">{t(item.labelKey)}</span>
        </Link>
      );
    });

  return (
    <nav className="flex flex-col gap-1">
      {render(COMPANY_NAV)}
      {isPlatformAdmin ? (
        <>
          <div className="my-2 border-t" />
          {render(PLATFORM_NAV)}
        </>
      ) : null}
    </nav>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const t = useTranslations('app');
  const [open, setOpen] = useState(false);

  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-40 flex h-14 items-center gap-3 border-b bg-background/95 px-4 backdrop-blur">
        <Sheet open={open} onOpenChange={setOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon" className="lg:hidden" aria-label={t('menu')}>
              <Menu className="size-5" aria-hidden />
            </Button>
          </SheetTrigger>
          <SheetContent side="start" className="w-72 p-0">
            <SheetTitle className="sr-only">{t('menu')}</SheetTitle>
            <div className="flex flex-col gap-4 p-4">
              <p className="text-sm font-semibold">{t('name')}</p>
              <CompanySwitcher />
              <NavLinks onNavigate={() => setOpen(false)} />
            </div>
          </SheetContent>
        </Sheet>

        <span className="text-sm font-semibold lg:hidden">{t('name')}</span>

        <div className="ms-auto flex items-center gap-2">
          <LanguageSwitcher />
          <UserMenu />
        </div>
      </header>

      <div className="flex flex-1">
        <aside className="hidden w-64 shrink-0 border-e bg-muted/30 lg:block">
          <div className="sticky top-14 flex flex-col gap-4 p-4">
            <p className="px-2 text-sm font-semibold">{t('name')}</p>
            <CompanySwitcher />
            <NavLinks />
          </div>
        </aside>

        <main className="min-w-0 flex-1 p-4 lg:p-6">{children}</main>
      </div>
    </div>
  );
}
