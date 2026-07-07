import { test, expect } from '@playwright/test';

test('profile selector is visible on map page', async ({ page }) => {
  await page.goto('/dashboard/map');
  await page.waitForLoadState('networkidle');
  const selector = page.locator('[data-testid="profile-selector"]').first();
  await expect(selector).toBeVisible();
  await expect(selector).toHaveValue('default');
});

test('free user switching profile on map shows paywall and reverts', async ({ page }) => {
  await page.goto('/dashboard/map');
  await page.waitForLoadState('networkidle');
  await page.locator('[data-testid="profile-selector"]').first().selectOption('diy_renovator');
  await expect(page.locator('[data-testid="paywall-modal"]')).toBeVisible();
  await page.locator('[data-testid="paywall-modal"] button:has-text("Not now")').click();
  await expect(page.locator('[data-testid="profile-selector"]').first()).toHaveValue('default');
});
