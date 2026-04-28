import { test, expect } from '@playwright/test';

test.describe('Dashboard Smoke Tests', () => {
  test('root page redirects to /dashboard', async ({ page }) => {
    const serverErrors: string[] = [];
    page.on('response', response => {
      if (response.status() >= 500 && response.status() !== 503) {
        serverErrors.push(`${response.status()} ${response.url()}`);
      }
    });

    await page.goto('/');
    await page.waitForURL(/\/dashboard/);

    expect(serverErrors.length).toBe(0);
  });

  test('dashboard listing page renders header and filter bar', async ({ page }) => {
    const serverErrors: string[] = [];
    page.on('response', response => {
      if (response.status() >= 500 && response.status() !== 503) {
        serverErrors.push(`${response.status()} ${response.url()}`);
      }
    });

    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('h1')).toContainText('Top Property Picks');
    await expect(page.locator('input[type="number"]').first()).toBeVisible();

    expect(serverErrors.length).toBe(0);
  });

  test('dashboard map page renders header', async ({ page }) => {
    const serverErrors: string[] = [];
    page.on('response', response => {
      if (response.status() >= 500 && response.status() !== 503) {
        serverErrors.push(`${response.status()} ${response.url()}`);
      }
    });

    await page.goto('/dashboard/map');
    await page.waitForLoadState('networkidle');
    await expect(page.locator('h1')).toContainText('Property Map');

    const mapOrEmpty = page.locator('.leaflet-container').or(page.locator('text=No listings match your filters'));
    await expect(mapOrEmpty.first()).toBeAttached({ timeout: 10000 });

    expect(serverErrors.length).toBe(0);
  });

  test('dashboard listing page is not stuck in loading state', async ({ page }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('text=Loading...')).toHaveCount(0, { timeout: 15000 });
  });

  test('dashboard map page is not stuck in loading state', async ({ page }) => {
    await page.goto('/dashboard/map');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('text=Loading...')).toHaveCount(0, { timeout: 15000 });
  });
});
