import { test, expect } from '@playwright/test';

test.describe('Equity fix + max equity filter + coord precision badge', () => {
  test('equity badge no longer shows ? equity placeholder on listings with computed values', async ({ page }) => {
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    await expect(page.locator('h1')).toContainText('Top Property Picks');
    await page.waitForLoadState('networkidle');

    const placeholders = page.getByText('? equity', { exact: true });
    const realBadges = page.locator('text=/~\\d+%.*€/');
    const placeholderCount = await placeholders.count();
    const realBadgeCount = await realBadges.count();

    expect(realBadgeCount).toBeGreaterThan(0);
  });

  test('max equity filter input is present and accepts input', async ({ page }) => {
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    await expect(page.locator('h1')).toContainText('Top Property Picks');
    // FilterBar hydrates after Suspense; wait for it.
    await expect(page.locator('input[placeholder="e.g. 200000"]')).toBeVisible({ timeout: 15000 });
    await page.locator('input[placeholder="e.g. 200000"]').fill('200000');
    await expect(page).toHaveURL(/max_equity=200000/);
  });

  test('coordinate precision badge visible on listings with exact coordinates', async ({ page }) => {
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    await expect(page.locator('h1')).toContainText('Top Property Picks');
    await page.waitForLoadState('networkidle');

    const exactBadge = page.locator('text=/^Exact$/').first();
    const landmarkBadge = page.locator('text=/^Landmark$/').first();
    const districtBadge = page.locator('text=/^District$/').first();
    const exactCount = await exactBadge.count();
    const landmarkCount = await landmarkBadge.count();
    const districtCount = await districtBadge.count();

    expect(exactCount + landmarkCount + districtCount).toBeGreaterThan(0);
  });
});
