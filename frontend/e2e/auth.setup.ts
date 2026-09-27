import { test as setup } from '@playwright/test';

import { STORAGE, signIn, type Who } from './helpers';

/**
 * Signs in once per role and saves the cookies, so the rest of the suite skips
 * the (deliberately expensive) password hash on every single test.
 */
for (const who of ['admin', 'entry', 'owner'] as Who[]) {
  setup(`authenticate as ${who}`, async ({ page }) => {
    await signIn(page, who);
    await page.context().storageState({ path: STORAGE[who] });
  });
}
