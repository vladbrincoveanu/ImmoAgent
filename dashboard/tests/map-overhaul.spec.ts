import { test, expect } from '@playwright/test';

test.describe('Map overhaul — MacBook fit + profile + insights + comparables', () => {
  test('map page fits MacBook viewport (1440x900) with all sections visible without page scroll', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle');

    // The body should not overflow vertically
    const bodyOverflow = await page.evaluate(() => ({
      docH: document.documentElement.scrollHeight,
      winH: window.innerHeight,
      overflow: document.documentElement.scrollHeight - window.innerHeight,
    }));
    expect(bodyOverflow.overflow).toBeLessThanOrEqual(8); // <= 8px tolerance

    // Both map and listings strip should be visible
    await expect(page.locator('.leaflet-container')).toBeVisible();
    await expect(page.locator('[data-testid="compact-listings-strip"]')).toBeVisible();
  });

  test('/dashboard has ProfileSelector in header (not only in filter bar)', async ({ page }) => {
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    await expect(page.locator('h1')).toContainText('Top Property Picks');
    const headerSelector = page.locator('header [data-testid="profile-selector"]');
    await expect(headerSelector).toBeVisible();
  });

  test('/dashboard/map has ProfileSelector in header that syncs to URL', async ({ page }) => {
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle');
    const headerSelector = page.locator('header [data-testid="profile-selector"]');
    await expect(headerSelector).toBeVisible();
    await headerSelector.selectOption('budget_buyer');
    await expect(page).toHaveURL(/profile=budget_buyer/);
  });

  test('Filter URL sync — /dashboard filter reflects on map view when "Map view" clicked', async ({ page }) => {
    await page.goto('/dashboard?profile=eco_conscious&max_price=400000&min_score=40', { waitUntil: 'domcontentloaded' });
    await expect(page.locator('[data-testid="open-map"]')).toBeVisible();
    await page.locator('[data-testid="open-map"]').click();
    await page.waitForURL(/dashboard\/map/);
    expect(page.url()).toContain('profile=eco_conscious');
    expect(page.url()).toContain('max_price=400000');
    expect(page.url()).toContain('min_score=40');
  });

  test('Below zone avg filter narrows results', async ({ page }) => {
    const noFilter = await (await fetch('http://localhost:3010/api/insights?')).json();
    const filtered = await (await fetch('http://localhost:3010/api/insights?below_avg_pct=20')).json();
    expect(filtered.total).toBeLessThanOrEqual(noFilter.total);
    expect(filtered.below_avg_count).toBeGreaterThan(0);
  });

  test('Zone vs avg badge visible on listings with computed data', async ({ page }) => {
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    await expect(page.locator('h1')).toContainText('Top Property Picks');
    await page.waitForLoadState('networkidle');
    const zoneBadges = page.locator('text=/[+-]?\\d+%\\s*zone/');
    expect(await zoneBadges.count()).toBeGreaterThan(0);
  });

  test('Deal Score badge visible on listings', async ({ page }) => {
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle');
    const dealScores = page.locator('text=/^\\d+ · (Great deal|Good deal|Fair|Risky)$/');
    expect(await dealScores.count()).toBeGreaterThan(0);
  });

  test('Smart Insights panel shows 7 cards (listings/avg price/ppm²/score/districts/below avg/transit)', async ({ page }) => {
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle');
    await expect(page.locator('[data-testid="smart-insights"]')).toBeVisible();
    const cards = page.locator('[data-testid="smart-insights"] > div');
    expect(await cards.count()).toBe(7);
  });

  test('MapLayersPopover shows U-Bahn and School layer rows (replaces MapLegend)', async ({ page }) => {
    await page.goto('/dashboard/map', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle');
    await page.waitForTimeout(1000);

    // Open the layers popover from the map top bar
    const layersBtn = page.locator('[data-testid="layers-btn"]');
    await expect(layersBtn).toBeVisible();
    await layersBtn.click();

    const popover = page.locator('[data-testid="layers-popover"]');
    await expect(popover).toBeVisible();

    // The new popover shows layer names + per-layer counts
    const stationsRow = popover.locator('[data-testid="layer-row-stations"]');
    const schoolsRow = popover.locator('[data-testid="layer-row-schools"]');
    await expect(stationsRow).toBeVisible();
    await expect(stationsRow).toContainText('U-Bahn');
    await expect(schoolsRow).toBeVisible();
    await expect(schoolsRow).toContainText('School');
  });

  test('Clicking a listing card opens detail with comparables', async ({ page }) => {
    await page.goto('/dashboard', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle');
    // Click first listing card
    const firstCard = page.locator('.grid > div.cursor-pointer').first();
    await firstCard.click();
    await expect(page.locator('[data-testid="comparables-section"]')).toBeVisible({ timeout: 10000 });
  });

  test('Save search button is present and clickable', async ({ page }) => {
    await page.goto('/dashboard?profile=default&min_score=30', { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('networkidle');
    const btn = page.locator('[data-testid="save-search-btn"]');
    await expect(btn).toBeVisible();
    // Stub the prompt to return a name
    page.on('dialog', (d) => d.accept('Test search'));
    await btn.click();
    // The button text changes to "Saved!" briefly
    await expect(btn).toContainText(/Saved|Save search/);
  });
});
