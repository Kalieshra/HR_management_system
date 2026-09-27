import { expect, type Page } from '@playwright/test';

export const DEMO = {
  admin: { email: 'admin@demo.test', password: 'DemoPass!2026' },
  entry: { email: 'entry@demo.test', password: 'DemoPass!2026' },
  owner: { email: 'owner@hrms.test', password: 'DemoPass!2026' },
};

export type Who = keyof typeof DEMO;

export const STORAGE = {
  admin: 'e2e/.auth/admin.json',
  entry: 'e2e/.auth/entry.json',
  owner: 'e2e/.auth/owner.json',
} as const;

const LABELS = {
  ar: { email: 'البريد الإلكتروني', password: 'كلمة المرور', submit: 'تسجيل الدخول' },
  en: { email: 'Email', password: 'Password', submit: 'Sign in' },
};

/**
 * Fill a field and make sure the value survives.
 *
 * The page is server-rendered, so a `fill` that lands before React hydrates is
 * wiped when the client mounts and resets the uncontrolled input. Retrying the
 * fill-and-assert pair rides out that window.
 */
export async function fillWhenReady(page: Page, label: string, value: string, exact = false) {
  const field = page.getByLabel(label, { exact });
  await expect(field).toBeVisible();
  await expect(async () => {
    await field.fill(value);
    await expect(field).toHaveValue(value);
  }).toPass({ timeout: 30_000 });
}

/**
 * Wait until the page is interactive.
 *
 * The submit button is rendered disabled and only enabled once React hydrates,
 * so it doubles as a reliable hydration signal — no arbitrary sleeps.
 */
export async function waitForHydration(page: Page, submitLabel: string) {
  await expect(page.getByRole('button', { name: submitLabel })).toBeEnabled({ timeout: 120_000 });
}

/** Sign in through the real form and wait for the app shell to appear. */
export async function signIn(page: Page, who: Who = 'admin', locale: 'ar' | 'en' = 'ar') {
  const user = DEMO[who];
  const labels = LABELS[locale];

  await page.goto(`/${locale}/login`);
  await waitForHydration(page, labels.submit);
  await fillWhenReady(page, labels.email, user.email);
  await fillWhenReady(page, labels.password, user.password, true);
  await page.getByRole('button', { name: labels.submit }).click();
  await page.waitForURL(new RegExp(`/${locale}/dashboard`), { timeout: 120_000 });
}

/** Assert the page is laid out for the given writing direction. */
export async function expectDirection(page: Page, dir: 'rtl' | 'ltr') {
  await expect(page.locator('html')).toHaveAttribute('dir', dir);
}
