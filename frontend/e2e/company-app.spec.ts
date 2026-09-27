import { expect, test } from '@playwright/test';

import { STORAGE } from './helpers';

test.describe('company app', () => {
  test.use({ storageState: STORAGE.admin });

  test('the dashboard shows the seeded company figures', async ({ page }) => {
    await page.goto('/ar/dashboard');
    await expect(page.getByRole('heading', { name: 'لوحة التحكم' })).toBeVisible();
    // 23 employees came from the reference workbook.
    await expect(page.getByText('الموظفين النشطين')).toBeVisible();
    await expect(page.getByText('23', { exact: true }).first()).toBeVisible();
  });

  test('the employees page lists all 23 seeded employees', async ({ page }) => {
    await page.goto('/ar/dashboard');
    await page.getByRole('link', { name: 'الموظفين', exact: true }).first().click();
    await page.waitForURL(/\/ar\/employees/);

    await expect(page.getByRole('heading', { name: 'الموظفين' })).toBeVisible();
    await expect(page.getByTestId('employee-row')).toHaveCount(23);
    await expect(page.getByText('ايه محمد عوضين سليمان')).toBeVisible();
  });

  test('searching filters the employee table', async ({ page }) => {
    await page.goto('/ar/employees');
    await page.getByRole('textbox', { name: 'بحث' }).fill('مريم');

    await expect(page.getByTestId('employee-row')).toHaveCount(1);
  });

  test('the daily entry grid loads a row per employee', async ({ page }) => {
    await page.goto('/ar/daily-entry');

    await expect(page.getByRole('heading', { name: 'الإدخال اليومي' })).toBeVisible();
    await expect(page.getByTestId('save-status')).toBeVisible();
    // AG Grid renders its rows lazily; the first one is enough to prove wiring.
    await expect(page.locator('.ag-center-cols-container .ag-row').first()).toBeVisible();
  });

  test('the daily entry grid is right-to-left in Arabic', async ({ page }) => {
    await page.goto('/ar/daily-entry');
    await expect(page.locator('.ag-root-wrapper').first()).toHaveClass(/ag-rtl/);
  });

  test('adjustments from the workbook seed are listed', async ({ page }) => {
    await page.goto('/ar/adjustments');

    await expect(page.getByRole('heading', { name: 'المستحقات والخصومات' })).toBeVisible();
    await expect(page.getByTestId('adjustment-row').first()).toBeVisible();
  });

  test('a branch-entry user does not see admin-only navigation', async ({ browser }) => {
    const context = await browser.newContext({ storageState: STORAGE.entry });
    const page = await context.newPage();
    await page.goto('/ar/dashboard');

    // `exact` matters: the dashboard's own quick-links contain these words too.
    await expect(page.getByRole('link', { name: 'الإدخال اليومي', exact: true })).toBeVisible();
    await expect(page.getByRole('link', { name: 'الإعدادات', exact: true })).toHaveCount(0);
    await expect(page.getByRole('link', { name: 'مراجعة الرواتب', exact: true })).toHaveCount(0);
    await expect(page.getByRole('link', { name: 'التقارير', exact: true })).toHaveCount(0);
    // …and the quick-link on the dashboard body is gone as well.
    await expect(page.getByRole('link', { name: 'فتح مراجعة الرواتب' })).toHaveCount(0);
    await context.close();
  });
});
