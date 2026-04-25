import { test, expect } from '@playwright/test';

test.describe('Dashboard Smoke Tests', () => {
  test('root page redirects to /dashboard', async ({ page }) => {
    const httpErrors: string[] = [];
    page.on('response', response => {
      if (response.status() >= 500) {
        httpErrors.push(`${response.status()} ${response.url()}`);
      }
    });

    await page.goto('/');
    await page.waitForURL(/\/dashboard/);

    expect(httpErrors.length).toBe(0);
  });

  test('dashboard listing page renders header and filter bar', async ({ page }) => {
    const httpErrors: string[] = [];
    page.on('response', response => {
      if (response.status() >= 500) {
        httpErrors.push(`${response.status()} ${response.url()}`);
      }
    });

    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');

    await expect(page.locator('h1')).toContainText('Top Property Picks');
    await expect(page.locator('input[type="number"]').first()).toBeVisible();

    expect(httpErrors.length).toBe(0);
  });

  test('dashboard map page renders header and nav', async ({ page }) => {
    const httpErrors: string[] = [];
    page.on('response', response => {
      if (response.status() >= 500) {
        httpErrors.push(`${response.status()} ${response.url()}`);
      }
    });

    await page.goto('/dashboard/map');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    await expect(page.locator('h1')).toContainText('Property Map');
    await expect(page.locator('a[href="/dashboard"]').first()).toBeVisible();

    expect(httpErrors.length).toBe(0);
  });

  test('dashboard listing page is not stuck in loading state', async ({ page }) => {
    await page.goto('/dashboard');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    expect(await page.locator('text=Loading...').count()).toBe(0);
  });

  test('dashboard map page is not stuck in loading state', async ({ page }) => {
    await page.goto('/dashboard/map');
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(3000);

    expect(await page.locator('text=Loading...').count()).toBe(0);
  });
});
