import createMiddleware from 'next-intl/middleware';
import { NextRequest, NextResponse } from 'next/server';

import { routing } from '@/i18n/routing';

const intlMiddleware = createMiddleware(routing);

/** Pages reachable without signing in. */
const PUBLIC_PAGES = ['/login', '/accept-invite', '/forgot-password', '/reset-password'];

const ACCESS_COOKIE = 'hrms_access';
const REFRESH_COOKIE = 'hrms_refresh';

function stripLocale(pathname: string): string {
  for (const locale of routing.locales) {
    if (pathname === `/${locale}`) return '/';
    if (pathname.startsWith(`/${locale}/`)) return pathname.slice(locale.length + 1);
  }
  return pathname;
}

function localeOf(pathname: string): string {
  for (const locale of routing.locales) {
    if (pathname === `/${locale}` || pathname.startsWith(`/${locale}/`)) return locale;
  }
  return routing.defaultLocale;
}

export default function middleware(request: NextRequest) {
  const response = intlMiddleware(request);

  const { pathname } = request.nextUrl;
  const path = stripLocale(pathname);
  const locale = localeOf(pathname);

  // Cookie presence is only a routing hint — the API verifies the JWT on every
  // request, so a forged cookie buys nothing but a redirect to a 401 screen.
  const signedIn = request.cookies.has(ACCESS_COOKIE) || request.cookies.has(REFRESH_COOKIE);
  const isPublic = PUBLIC_PAGES.some((page) => path === page || path.startsWith(`${page}/`));

  if (!signedIn && !isPublic) {
    const url = new URL(`/${locale}/login`, request.url);
    if (path !== '/') url.searchParams.set('next', path);
    return NextResponse.redirect(url);
  }

  if (signedIn && (path === '/login' || path === '/')) {
    return NextResponse.redirect(new URL(`/${locale}/dashboard`, request.url));
  }

  return response;
}

export const config = {
  matcher: '/((?!api|_next|_vercel|.*\\..*).*)',
};
