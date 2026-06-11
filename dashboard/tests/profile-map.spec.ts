import { test, expect } from '@playwright/test';

test('profile selector is visible on map page', async ({ page }) => {
  await page.goto('/dashboard/map?profile=urban_professional');
  await page.waitForLoadState('networkidle');
  const selector = page.locator('[data-testid="profile-selector"]');
  await expect(selector).toBeVisible();
  await expect(selector).toHaveValue('urban_professional');
});

test('switching profile on map updates URL and selector', async ({ page }) => {
  await page.goto('/dashboard/map?profile=default');
  await page.waitForLoadState('networkidle');
  await page.selectOption('[data-testid="profile-selector"]', 'eco_conscious');
  await page.waitForURL(/profile=eco_conscious/);
  await expect(page.locator('[data-testid="profile-selector"]')).toHaveValue('eco_conscious');
});
