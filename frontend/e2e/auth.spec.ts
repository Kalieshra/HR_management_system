import { expect, test } from '@playwright/test';

import { DEMO, expectDirection, fillWhenReady, signIn, waitForHydration } from './helpers';

test.describe('authentication', () => {
  // These exercise signing in, so they must start with no session at all.
  test.use({ storageState: { cookies: [], origins: [] } });

  test('an anonymous visitor is sent to the sign-in page', async ({ page }) => {
    await page.goto('/ar/employees');

    await expect(page).toHaveURL(/\/ar\/login/);
    await expect(page.getByRole('button', { name: 'تسجيل الدخول' })).toBeVisible();
  });

  test('the sign-in page is right-to-left in Arabic and left-to-right in English', async ({
    page,
  }) => {
    await page.goto('/ar/login');
    await expectDirection(page, 'rtl');
    await expect(page.locator('html')).toHaveAttribute('lang', 'ar');

    await page.goto('/en/login');
    await expectDirection(page, 'ltr');
    await expect(page.locator('html')).toHaveAttribute('lang', 'en');
  });

  test('the submit button becomes usable, and says so while it is not', async ({ page }) => {
    // Two real bugs guarded here. Clicking before hydration used to perform the
    // form's *native* GET submit, putting the password in the URL — so the
    // button is disabled until React attaches. But a plain disabled button
    // looks broken, so while it waits it must read as busy, not as dead.
    await page.goto('/ar/login', { waitUntil: 'commit' });

    const starting = page.getByRole('button', { name: 'جارٍ تجهيز الصفحة…' });
    if (await starting.count()) {
      await expect(starting).toHaveAttribute('aria-busy', 'true');
    }

    await expect(page.getByRole('button', { name: 'تسجيل الدخول' })).toBeEnabled();
  });

  test('the form posts rather than getting, so fields cannot reach the URL', async ({ page }) => {
    await page.goto('/ar/login');
    await expect(page.locator('form')).toHaveAttribute('method', 'post');
  });

  test('the password is never placed in the URL', async ({ page }) => {
    const urls: string[] = [];
    page.on('framenavigated', (frame) => urls.push(frame.url()));

    await signIn(page, 'admin');

    for (const url of urls) {
      expect(url, `credentials leaked into ${url}`).not.toContain('password=');
      expect(url).not.toContain(DEMO.admin.password);
    }
  });

  test('a wrong password is rejected with a readable message', async ({ page }) => {
    await page.goto('/ar/login');
    await waitForHydration(page, 'تسجيل الدخول');
    await fillWhenReady(page, 'البريد الإلكتروني', DEMO.admin.email);
    await fillWhenReady(page, 'كلمة المرور', 'definitely-wrong', true);
    await page.getByRole('button', { name: 'تسجيل الدخول' }).click();

    await expect(page.getByRole('alert')).toBeVisible();
    await expect(page).toHaveURL(/\/ar\/login/);
  });

  test('a company admin can sign in and lands on the dashboard', async ({ page }) => {
    await signIn(page, 'admin');

    await expect(page.getByRole('heading', { name: 'لوحة التحكم' })).toBeVisible();
    await expect(page.getByText('الشركة التجريبية')).toBeVisible();
  });

  test('the auth token is stored in an HttpOnly cookie, never in JS', async ({ page, context }) => {
    await signIn(page, 'admin');

    const cookies = await context.cookies();
    const access = cookies.find((cookie) => cookie.name === 'hrms_access');
    expect(access, 'access cookie should exist').toBeTruthy();
    expect(access?.httpOnly).toBe(true);

    // The page itself must not be able to read it.
    const visible = await page.evaluate(() => document.cookie);
    expect(visible).not.toContain('hrms_access');
  });

  test('signing out returns the user to the sign-in page', async ({ page }) => {
    await signIn(page, 'admin');

    await page.getByRole('button', { name: /مدير الشركة|admin@demo.test/ }).click();
    await page.getByRole('menuitem', { name: 'تسجيل الخروج' }).click();

    await expect(page).toHaveURL(/\/ar\/login/);
    await page.goto('/ar/dashboard');
    await expect(page).toHaveURL(/\/ar\/login/);
  });
});
