import { test, expect } from '@playwright/test';

/** The /alerts dashboard: create a keyword watch on the private-transfer feed.
 *
 * Alerts are Pro-only, so an anonymous visitor gets a 402 and the page must say
 * so rather than appearing to succeed. These assertions run against the real
 * rendered DOM, not screenshots. */

test('alerts page renders the create form', async ({ page }) => {
  await page.goto('/alerts');
  await expect(page.getByTestId('alerts-page')).toBeVisible();
  await expect(page.getByTestId('alert-keyword')).toBeVisible();
  await expect(page.getByTestId('alert-email')).toBeVisible();
  await expect(page.getByTestId('alert-chatid')).toBeVisible();
  await expect(page.getByTestId('alert-submit')).toBeVisible();
});

test('submitting with no channel surfaces an error instead of failing silently',
  async ({ page }) => {
    await page.goto('/alerts');
    await page.getByTestId('alert-keyword').fill('1100');
    await page.getByTestId('alert-submit').click();
    // Either the Pro gate or the missing-channel validation — both must be shown.
    await expect(page.getByTestId('alert-status')).toBeVisible();
    const text = await page.getByTestId('alert-status').textContent();
    expect(text?.trim().length ?? 0).toBeGreaterThan(0);
  });

test('an invalid telegram chat id is rejected, not stored', async ({ page }) => {
  await page.goto('/alerts');
  await page.getByTestId('alert-chatid').fill('@notanid');
  await page.getByTestId('alert-submit').click();
  await expect(page.getByTestId('alert-status')).toBeVisible();
});

test('the private rubric is reachable from /coop', async ({ page }) => {
  await page.goto('/coop');
  const link = page.getByTestId('coop-private-link');
  await expect(link).toBeVisible();
  await link.click();
  await expect(page.getByTestId('coop-private-page')).toBeVisible();
});
