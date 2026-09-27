import { expect, test, type BrowserContext } from '@playwright/test';

import { STORAGE } from './helpers';

/**
 * The access cookie lives 30 minutes, the refresh cookie 14 days. Dropping the
 * first and keeping the second is exactly what the browser does on its own once
 * the access token ages out — and it used to strand the user in a signed-in
 * shell with no session: `/auth/me` answered 401, so the company switcher, the
 * admin links and every data query silently emptied, while the Next middleware
 * kept letting them in on the strength of the refresh cookie.
 */
async function expireAccessCookie(context: BrowserContext) {
  const kept = (await context.cookies()).filter((cookie) => cookie.name !== 'hrms_access');
  await context.clearCookies();
  await context.addCookies(kept);
}

test.describe('session lifetime', () => {
  test('an expired access token is refreshed instead of emptying the app', async ({ browser }) => {
    const context = await browser.newContext({ storageState: STORAGE.admin });
    await expireAccessCookie(context);

    const page = await context.newPage();
    await page.goto('/ar/dashboard');

    // All three come from `/auth/me`, so they prove the session was restored
    // rather than quietly lost: the company name, an admin-only link, and the
    // dashboard's own data.
    await expect(page.getByText('الشركة التجريبية')).toBeVisible();
    await expect(page.getByRole('link', { name: 'مراجعة الرواتب' })).toBeVisible();
    await expect(page.getByText('الموظفين النشطين')).toBeVisible();

    await context.close();
  });

  test('the refreshed session survives a reload', async ({ browser }) => {
    const context = await browser.newContext({ storageState: STORAGE.admin });
    await expireAccessCookie(context);

    const page = await context.newPage();
    await page.goto('/ar/employees');
    await expect(page.getByRole('link', { name: 'مراجعة الرواتب' })).toBeVisible();

    // A single refresh must replace the cookie for good, not per request.
    const access = (await context.cookies()).find((cookie) => cookie.name === 'hrms_access');
    expect(access, 'a fresh access cookie should have been stored').toBeTruthy();
    expect(access?.httpOnly).toBe(true);

    await context.close();
  });

  test('a session that cannot be refreshed lands on the sign-in page', async ({ browser }) => {
    const context = await browser.newContext({ storageState: STORAGE.admin });
    await context.clearCookies();
    // A refresh cookie the backend will reject. The middleware sees a cookie and
    // lets the page through, so only the client can discover the session is dead
    // — and it must say so instead of rendering an app that does nothing.
    await context.addCookies([
      { name: 'hrms_refresh', value: 'not-a-real-token', domain: 'localhost', path: '/' },
    ]);

    const page = await context.newPage();
    await page.goto('/ar/dashboard');

    await expect(page).toHaveURL(/\/ar\/login/, { timeout: 60_000 });
    await context.close();
  });
});

test.describe('platform owner without a membership', () => {
  // `owner@hrms.test` is a platform admin who belongs to no company. The backend
  // grants them every tenant (`resolve_company` lets a platform admin through
  // with a `None` membership), but the frontend used to build the switcher from
  // `session.memberships` alone — so they saw an app with no company at all.
  test.use({ storageState: STORAGE.owner });

  test('can pick a company and read its dashboard', async ({ page }) => {
    await page.goto('/ar/dashboard');

    await expect(page.getByText('الشركة التجريبية')).toBeVisible();
    await expect(page.getByText('الموظفين النشطين')).toBeVisible();
  });

  test('sees the platform link and the company-admin links', async ({ page }) => {
    await page.goto('/ar/dashboard');

    await expect(page.getByRole('link', { name: 'إدارة المنصة' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'مراجعة الرواتب' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'الإعدادات' })).toBeVisible();
  });
});
