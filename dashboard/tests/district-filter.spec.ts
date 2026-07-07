import { test, expect } from '@playwright/test';

test.describe('District filter roundtrip', () => {
  test('2-digit district input updates URL', async ({ page }) => {
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    await expect(page.locator('h1')).toContainText('Top Property Picks');
    const districtInput = page.locator('input[placeholder="e.g. 02"]');
    await expect(districtInput).toBeVisible({ timeout: 15000 });
    await districtInput.fill('02');
    await expect(page).toHaveURL(/district=02/);
  });

  test('4-digit district input updates URL', async ({ page }) => {
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    await expect(page.locator('h1')).toContainText('Top Property Picks');
    const districtInput = page.locator('input[placeholder="e.g. 02"]');
    await expect(districtInput).toBeVisible({ timeout: 15000 });
    await districtInput.fill('1020');
    await expect(page).toHaveURL(/district=1020/);
  });

  test('district + profile compound: API call carries both, then Pro gate paywalls free user', async ({ page }) => {
    const apiCalls: string[] = [];
    page.on('request', (req) => {
      const url = req.url();
      if (url.includes('/api/listings/top')) apiCalls.push(url);
    });
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    await expect(page.locator('h1')).toContainText('Top Property Picks');
    const districtInput = page.locator('input[placeholder="e.g. 02"]');
    await expect(districtInput).toBeVisible({ timeout: 15000 });
    await districtInput.fill('15');
    await page.locator('[data-testid="profile-selector"]').first().selectOption('growing_family');
    // The compound request is issued (district + profile in one call)...
    await expect
      .poll(() => apiCalls.find((u) => u.includes('district=15') && u.includes('profile=growing_family')))
      .toBeTruthy();
    // ...but personas are Pro-only: free user gets the paywall and reverts to default
    await expect(page.locator('[data-testid="paywall-modal"]')).toBeVisible();
    await page.locator('[data-testid="paywall-modal"] button:has-text("Not now")').click();
    await expect(page).toHaveURL(/district=15/);
    await expect(page).not.toHaveURL(/profile=/);
  });

  test('district + legacy profile alias + maxPrice: alias normalizes, rest persists across reload', async ({ page }) => {
    await page.goto('/dashboard?district=02&profile=owner_occupier&max_price=400000', { waitUntil: 'domcontentloaded' });
    await expect(page.locator('h1')).toContainText('Top Property Picks');
    const districtInput = page.locator('input[placeholder="e.g. 02"]');
    await expect(districtInput).toBeVisible({ timeout: 15000 });
    await expect(districtInput).toHaveValue('02');
    // owner_occupier was consolidated into default (free) — no paywall
    await expect(page.locator('[data-testid="profile-selector"]').first()).toHaveValue('default');
    await expect(page.locator('[data-testid="paywall-modal"]')).not.toBeVisible();
    await page.reload();
    await expect(page).toHaveURL(/district=02/);
    await expect(page).toHaveURL(/max_price=400000/);
    await expect(districtInput).toHaveValue('02');
    await expect(page.locator('[data-testid="profile-selector"]').first()).toHaveValue('default');
  });
});
