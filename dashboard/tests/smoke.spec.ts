import { test, expect, type Page } from '@playwright/test';

async function login(page: Page) {
  await page.goto('/login');
  await page.fill('input[id="username"]', 'test');
  await page.fill('input[id="password"]', 'test123');
  await page.click('button[type="submit"]');
  await page.waitForURL(/\/dashboard/, { timeout: 10000 });
}

test.describe('Dashboard Smoke Tests', () => {
  test.beforeEach(async ({ page }) => {
    await login(page);
  });

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

    const mapVisible = await page.locator('.leaflet-container').isVisible().catch(() => false);
    if (!mapVisible) {
      await expect(page.locator('text=No listings match your filters').first()).toBeVisible({ timeout: 10000 });
    }

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
