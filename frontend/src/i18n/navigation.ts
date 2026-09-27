import { createNavigation } from 'next-intl/navigation';

import { routing } from './routing';

/**
 * Locale-aware replacements for next/link and next/navigation. Using these
 * keeps the current locale when navigating and lets the language switcher
 * swap locales while staying on the same path.
 */
export const { Link, redirect, usePathname, useRouter, getPathname } = createNavigation(routing);
