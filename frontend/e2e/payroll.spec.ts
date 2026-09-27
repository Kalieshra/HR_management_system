import { expect, test } from '@playwright/test';

import { STORAGE } from './helpers';

/** The seeded demo month reproduces the reference workbook exactly. */
const WORKBOOK_TOTALS = {
  base_salary: '162,500.00',
  total_earnings: '156,959.26',
  total_deductions: '42,220.37',
  net_salary: '114,738.89',
};

test.describe('payroll review', () => {
  test.use({ storageState: STORAGE.admin });

  test.beforeEach(async ({ page }) => {
    await page.goto('/ar/payroll/2026/2');
  });

  test('the review grid shows the workbook totals to the cent', async ({ page }) => {
    await expect(page.getByTestId('payroll-totals')).toBeVisible();

    for (const [field, value] of Object.entries(WORKBOOK_TOTALS)) {
      await expect(page.getByTestId(`total-${field}`)).toHaveText(value);
    }
  });

  test('the grid uses the workbook column names and groups', async ({ page }) => {
    // The report is 34 columns wide, so AG Grid only renders what is on screen.
    await expect(
      page.locator('.ag-header-group-cell').filter({ hasText: 'الاستحقاق' }),
    ).toBeVisible();
    await expect(
      page.locator('.ag-header-cell-text').filter({ hasText: 'قيمة ايام العمل' }),
    ).toBeVisible();

    // Scroll the way a user reads across the sheet, into the deductions block.
    // Under `dir="rtl"` Chrome counts scrollLeft downwards from 0, so the far
    // end of the columns is a negative offset.
    const viewport = page.locator('.ag-body-horizontal-scroll-viewport');
    const scrollTo = (fraction: number) =>
      viewport.evaluate((element, ratio) => {
        const distance = element.scrollWidth * ratio;
        element.scrollLeft = distance;
        if (element.scrollLeft === 0 && ratio !== 0) element.scrollLeft = -distance;
      }, fraction);

    await scrollTo(0.5);
    await expect(
      page.locator('.ag-header-group-cell').filter({ hasText: 'الاستقطاع' }),
    ).toBeVisible();

    await scrollTo(1);
    await expect(
      page.locator('.ag-header-cell-text').filter({ hasText: 'صافى الراتب' }),
    ).toBeVisible();
  });

  test('overridden cells are highlighted', async ({ page }) => {
    // The seeder pins the workbook's attendance figures as explicit overrides.
    await expect(page.locator('.cell-overridden').first()).toBeVisible();
  });

  test('a month can be closed and reopened', async ({ page }) => {
    await page.getByRole('button', { name: 'إغلاق الشهر' }).click();
    await expect(page.getByText('مغلق', { exact: true })).toBeVisible();

    await page.getByRole('button', { name: 'إعادة الفتح' }).click();
    await expect(page.getByRole('button', { name: 'إغلاق الشهر' })).toBeVisible();
  });

  test('a closed month refuses new daily entry', async ({ page }) => {
    await page.getByRole('button', { name: 'إغلاق الشهر' }).click();
    await expect(page.getByText('مغلق', { exact: true })).toBeVisible();

    await page.goto('/ar/daily-entry');
    await page.getByLabel('التاريخ').fill('2026-02-10');
    await page.getByRole('button', { name: 'تعيين الكل حاضر' }).click();

    await expect(page.getByText('هذا الشهر مغلق. أعد فتحه قبل إجراء أي تعديل.')).toBeVisible();

    // Leave the fixture as we found it.
    await page.goto('/ar/payroll/2026/2');
    await page.getByRole('button', { name: 'إعادة الفتح' }).click();
    await expect(page.getByRole('button', { name: 'إغلاق الشهر' })).toBeVisible();
  });

  test('an Excel report can be generated and appears in the history', async ({ page }) => {
    const popup = page.waitForEvent('popup').catch(() => null);
    await page.getByRole('button', { name: 'تنزيل الإكسل' }).click();
    await expect(page.getByText('تم إنشاء التقرير.')).toBeVisible();
    await popup;

    await page.goto('/ar/reports');
    await expect(page.getByTestId('report-row').first()).toBeVisible();
  });
});
