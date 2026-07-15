import { test, expect } from '@playwright/test';

test('profile selector is visible on dashboard', async ({ page }) => {
  await page.goto('/dashboard');
  await page.waitForLoadState('networkidle');
  const selector = page.locator('[data-testid="profile-selector"]');
  await expect(selector).toBeVisible();
  await expect(selector).toHaveValue('default');
});

test('switching profile updates URL and selector value', async ({ page }) => {
  await page.goto('/dashboard');
  await page.waitForLoadState('networkidle');
  await page.selectOption('[data-testid="profile-selector"]', 'owner_occupier');
  await page.waitForURL(/profile=owner_occupier/);
  await expect(page.locator('[data-testid="profile-selector"]')).toHaveValue('owner_occupier');
});

test('profile URL param persists across refresh', async ({ page }) => {
  await page.goto('/dashboard?profile=urban_professional');
  await expect(page.locator('[data-testid="profile-selector"]')).toHaveValue('urban_professional');
  await page.reload();
  await expect(page).toHaveURL(/profile=urban_professional/);
  await expect(page.locator('[data-testid="profile-selector"]')).toHaveValue('urban_professional');
});

test('invalid profile in URL falls back to default', async ({ page }) => {
  await page.goto('/dashboard?profile=garbage');
  await page.waitForLoadState('networkidle');
  await expect(page.locator('[data-testid="profile-selector"]')).toHaveValue('default');
});
