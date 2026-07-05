import { test, expect } from '@playwright/test';

test.describe('Dashboard Smoke Tests', () => {
  // `/` is the marketing landing page (since 8eb7748), no longer a redirect.
  test('root page renders landing with a path into the dashboard', async ({ page }) => {
    const serverErrors: string[] = [];
    page.on('response', response => {
      if (response.status() >= 500 && response.status() !== 503) {
        serverErrors.push(`${response.status()} ${response.url()}`);
      }
    });

    await page.goto('/');
    await expect(page.locator('a[href*="/dashboard"]').first()).toBeVisible();

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

    // Scope to the desktop instance — the first .leaflet-container in the DOM
    // can be the hidden mobile one (dual-map layout), which reads as invisible.
    await expect(page.locator('.map-desktop .leaflet-container')).toBeVisible({ timeout: 10000 });

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
