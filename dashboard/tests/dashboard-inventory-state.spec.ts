import { test, expect, type Page } from '@playwright/test';

async function mockInsights(page: Page) {
  await page.route('**/api/insights**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        total: 0,
        visible: 0,
        unfinanceable_count: 0,
        avg_price: null,
        avg_price_per_m2: null,
        avg_score: null,
        district_count: 0,
        below_avg_count: 0,
        good_transit_count: 0,
        best_deal_pct: 0,
      }),
    });
  });
}

test('empty purchase inventory explains the state and links to co-op inventory', async ({ page }) => {
  await page.route('**/api/listings/top**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ listings: [], total: 0 }),
    });
  });
  await mockInsights(page);

  await page.goto('/dashboard');

  await expect(page.getByTestId('dashboard-empty')).toBeVisible();
  await expect(page.getByRole('heading', { name: 'No active purchase listings' })).toBeVisible();
  await expect(page.getByRole('link', { name: 'Browse co-op flats' })).toHaveAttribute('href', '/coop');
  await expect(page.getByText('No listings found.')).toHaveCount(0);
});

test('listing API failure shows retry state instead of empty inventory state', async ({ page }) => {
  await page.route('**/api/listings/top**', async (route) => {
    await route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ error: 'Database unavailable' }),
    });
  });
  await mockInsights(page);

  await page.goto('/dashboard');

  await expect(page.getByTestId('dashboard-error')).toBeVisible();
  await expect(page.getByRole('button', { name: 'Retry loading listings' })).toBeVisible();
  await expect(page.getByTestId('dashboard-empty')).toHaveCount(0);
});
