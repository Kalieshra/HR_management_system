import { expect, test } from '@playwright/test';

import { STORAGE } from './helpers';

test.describe('platform administration', () => {
  test('the platform owner sees aggregate stats', async ({ browser }) => {
    const context = await browser.newContext({ storageState: STORAGE.owner });
    const page = await context.newPage();
    await page.goto('/ar/platform');

    await expect(page.getByRole('heading', { name: 'إدارة المنصة' })).toBeVisible();
    await expect(page.getByText('الشركات', { exact: true }).first()).toBeVisible();
    await context.close();
  });

  test('the platform owner can list companies', async ({ browser }) => {
    const context = await browser.newContext({ storageState: STORAGE.owner });
    const page = await context.newPage();
    await page.goto('/ar/platform/companies');

    await expect(page.getByTestId('company-row').first()).toBeVisible();
    // Scoped to the table: the platform owner now also carries the company in
    // the sidebar switcher, so a bare text match hits two elements.
    await expect(page.getByRole('cell', { name: 'الشركة التجريبية' })).toBeVisible();
    await context.close();
  });

  test('a company admin cannot reach the platform pages', async ({ browser }) => {
    const context = await browser.newContext({ storageState: STORAGE.admin });
    const page = await context.newPage();
    await page.goto('/ar/platform/companies');

    // No platform link in the sidebar, and the API refuses the data.
    await expect(page.getByRole('link', { name: 'إدارة المنصة', exact: true })).toHaveCount(0);
    await expect(page.getByTestId('company-row')).toHaveCount(0);
    await context.close();
  });
});

test.describe('settings', () => {
  test.use({ storageState: STORAGE.admin });

  test('branches from the workbook seed are listed', async ({ page }) => {
    await page.goto('/ar/settings');

    await expect(page.getByRole('heading', { name: 'الإعدادات' })).toBeVisible();
    await expect(page.getByTestId('branch-row').first()).toBeVisible();
    await expect(page.getByText('فرع اسماعليه').first()).toBeVisible();
  });

  test('the payroll policy shows the workbook defaults', async ({ page }) => {
    await page.goto('/ar/settings');
    await page.getByRole('tab', { name: 'سياسة الرواتب' }).click();

    await expect(page.getByLabel('عدد أيام الشهر')).toHaveValue('30');
    await expect(page.getByLabel('نسبة خصم المرضي')).toHaveValue('0.2500');
    await expect(page.getByLabel('نسبة التأمينات')).toHaveValue('0.1100');
  });
});
