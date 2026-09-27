import { defineRouting } from 'next-intl/routing';

/**
 * Arabic is the product's default language; English is the alternative.
 * Every route is prefixed (`/ar/...`, `/en/...`) so the active locale is
 * always explicit and shareable.
 */
export const routing = defineRouting({
  locales: ['ar', 'en'],
  defaultLocale: 'ar',
  localePrefix: 'always',
});

export type Locale = (typeof routing.locales)[number];

/** Text direction for a locale — drives `<html dir>` and AG Grid's `enableRtl`. */
export function directionFor(locale: string): 'rtl' | 'ltr' {
  return locale === 'ar' ? 'rtl' : 'ltr';
}
