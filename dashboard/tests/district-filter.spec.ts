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

  test('district + profile compound: both appear in URL and trigger API call', async ({ page }) => {
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
    await page.locator('[data-testid="profile-selector"]').first().selectOption('owner_occupier');
    await expect(page).toHaveURL(/district=15/);
    await expect(page).toHaveURL(/profile=owner_occupier/);
    const compoundCall = apiCalls.find((u) => u.includes('district=15') && u.includes('profile=owner_occupier'));
    expect(compoundCall).toBeTruthy();
  });

  test('district + profile + maxPrice all persist across reload', async ({ page }) => {
    await page.goto('/dashboard?district=02&profile=owner_occupier&max_price=400000', { waitUntil: 'domcontentloaded' });
    await expect(page.locator('h1')).toContainText('Top Property Picks');
    const districtInput = page.locator('input[placeholder="e.g. 02"]');
    await expect(districtInput).toBeVisible({ timeout: 15000 });
    await expect(districtInput).toHaveValue('02');
    await expect(page.locator('[data-testid="profile-selector"]').first()).toHaveValue('owner_occupier');
    await page.reload();
    await expect(page).toHaveURL(/district=02/);
    await expect(page).toHaveURL(/profile=owner_occupier/);
    await expect(page).toHaveURL(/max_price=400000/);
    await expect(districtInput).toHaveValue('02');
    await expect(page.locator('[data-testid="profile-selector"]').first()).toHaveValue('owner_occupier');
  });
});
