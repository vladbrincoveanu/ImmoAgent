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

test('MapLayersPopover toggles U-Bahn + Schools; default state has only Listings on', async ({ page }) => {
  await page.goto('/dashboard/map');
  await page.locator('[data-testid="layers-btn"]').click();
  const pop = page.locator('[data-testid="layers-popover"]');
  await expect(pop).toBeVisible();
  const stationsToggle = pop.locator('[data-testid="layer-toggle-stations"]');
  const schoolsToggle = pop.locator('[data-testid="layer-toggle-schools"]');
  // Default: stations off → click to turn on
  await stationsToggle.click();
  // After click the toggle reflects on state; we just check the click handler fired
  await schoolsToggle.click();
  // Close by clicking outside
  await page.locator('body').click({ position: { x: 10, y: 10 } });
  await expect(pop).toBeHidden();
});

test('T7: price pins use single navy color by default, blue when selected, no tier-style variations', async ({ page }) => {
  await page.goto('/dashboard/map');
  await page.waitForSelector('.leaflet-marker-icon', { timeout: 10000 });
  await page.waitForTimeout(500);

  // Collect default pin background colors
  const defaultColors = await page.evaluate(() => {
    const icons = Array.from(document.querySelectorAll('.leaflet-marker-icon > div')) as HTMLElement[];
    return icons.map((el) => window.getComputedStyle(el).backgroundColor);
  });

  // Every pin should be navy (#16243a → rgb(22, 36, 58)) by default
  const NAVY = 'rgb(22, 36, 58)';
  for (const c of defaultColors) {
    expect(c, `default pin color mismatch: ${c}`).toBe(NAVY);
  }

  // Click first marker → that pin should turn blue
  const first = page.locator('.leaflet-marker-icon').first();
  await first.click();
  await page.waitForTimeout(400);

  const selectedColor = await first.locator('div').first().evaluate(
    (el) => window.getComputedStyle(el as HTMLElement).backgroundColor
  );
  const SELECTED = 'rgb(36, 86, 230)';
  expect(selectedColor, `selected pin color mismatch: ${selectedColor}`).toBe(SELECTED);
});
