import { test, expect } from '@playwright/test';

test('ListingRail renders at 340px width with count + sort header', async ({ page }) => {
  await page.goto('/dashboard/map');
  const rail = page.locator('[data-testid="listing-rail"]');
  await expect(rail).toBeVisible();
  const box = await rail.boundingBox();
  expect(box).not.toBeNull();
  expect(box?.width).toBe(340);
  await expect(rail.locator('[data-testid="rail-count"]')).toContainText(/\d+ in view/);
  await expect(rail.locator('[data-testid="rail-sort"]')).toBeVisible();
});

test('MapTopBar shows brand "Immo Scouter", Filters button with badge, Layers button', async ({ page }) => {
  await page.goto('/dashboard/map');
  const top = page.locator('[data-testid="map-top-bar"]');
  await expect(top).toBeVisible();
  const box = await top.boundingBox();
  expect(box?.height).toBe(56);
  await expect(top.locator('[data-testid="brand"]')).toHaveText('Immo Scouter');
  await expect(top.locator('[data-testid="filters-btn"]')).toBeVisible();
  await expect(top.locator('[data-testid="layers-btn"]')).toBeVisible();
});

test('MapFilterPopover opens on Filters click, Apply sets badge, closes popover', async ({ page }) => {
  await page.goto('/dashboard/map');
  await page.locator('[data-testid="filters-btn"]').click();
  const pop = page.locator('[data-testid="filter-popover"]');
  await expect(pop).toBeVisible();
  await pop.locator('[data-testid="filter-min-score"]').fill('25');
  await pop.locator('[data-testid="filter-apply"]').click();
  await expect(pop).toBeHidden();
  await expect(page.locator('[data-testid="filter-count-badge"]')).toHaveText('1');
});
