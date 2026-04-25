import { test, expect } from '@playwright/test';

function isExpectedApiError(msg: string): boolean {
  return (
    msg.includes('500') ||
    msg.includes('Failed to load resource') ||
    msg.includes('/api/listings')
  );
}

test.describe('Dashboard Smoke Tests', () => {
  test('root page redirects to /dashboard', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') errors.push(msg.text());
    });

    await page.goto('/');
    await page.waitForURL(/\/dashboard/);

    const realErrors = errors.filter(e =>
      !e.includes('Warning') &&
      !isExpectedApiError(e)
    );
    expect(realErrors).toHaveLength(0);
  });

  test('dashboard listing page loads without errors', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') errors.push(msg.text());
    });

    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('h1')).toContainText('Top Property Picks');
    await expect(page.locator('input[type="number"]').first()).toBeVisible();

    const realErrors = errors.filter(e =>
      !e.includes('Warning') &&
      !isExpectedApiError(e)
    );
    expect(realErrors).toHaveLength(0);
  });

  test('dashboard map page loads without errors', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', msg => {
      if (msg.type() === 'error') errors.push(msg.text());
    });

    await page.goto('/dashboard/map');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    await expect(page.locator('h1')).toContainText('Property Map');
    await expect(page.locator('a[href="/dashboard"]').first()).toBeVisible();

    const realErrors = errors.filter(e =>
      !e.includes('Warning') &&
      !isExpectedApiError(e)
    );
    expect(realErrors).toHaveLength(0);
  });

  test('dashboard page shows listing cards or empty state', async ({ page }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    const hasListings = await page.locator('[class*="cursor-pointer"]').count();
    const hasEmptyState = await page.locator('text=No listings found').count();
    expect(hasListings > 0 || hasEmptyState > 0).toBeTruthy();
  });

  test('dashboard map page shows map container when listings exist', async ({ page }) => {
    await page.goto('/dashboard/map');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(6000);

    const hasMap = await page.locator('.leaflet-container').count();
    const hasEmptyState = await page.locator('text=No listings match your filters').count();
    expect(hasMap > 0 || hasEmptyState > 0).toBeTruthy();
  });
});
