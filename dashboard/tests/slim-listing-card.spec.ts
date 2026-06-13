import { test, expect } from '@playwright/test';

test('SlimListingCard shows thumb, price, title, m²/€/m², score chip — no zone-delta', async ({ page }) => {
  await page.goto('/dashboard/map');
  const card = page.locator('[data-testid="slim-listing-card"]').first();
  await expect(card).toBeVisible();
  await expect(card.locator('[data-testid="price"]')).toBeVisible();
  await expect(card.locator('[data-testid="title"]')).toBeVisible();
  await expect(card.locator('[data-testid="sub"]')).toContainText('m²');
  await expect(card.locator('[data-testid="score"]')).toBeVisible();
  await expect(card.locator('[data-testid="zone-delta"]')).toHaveCount(0);
  await expect(card.locator('[data-testid="address"]')).toHaveCount(0);
});
