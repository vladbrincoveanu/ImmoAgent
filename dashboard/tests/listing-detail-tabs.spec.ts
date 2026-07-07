import { test, expect, Page } from '@playwright/test';

// Opens the ListingDetail modal via: pin → SelectedCard → "View listing" CTA.
async function openDetailModal(page: Page) {
  await page.goto('/dashboard/map');
  await page.waitForSelector('.leaflet-marker-icon', { timeout: 10000 });
  // dispatchEvent: overlapping pins at city zoom intercept a positional click.
  await page.locator('.leaflet-marker-icon').first().dispatchEvent('click');
  await page.waitForTimeout(300);
  await page.locator('[data-testid="view-listing-cta"]').click();
  await expect(page.locator('[data-testid="panel-overview"]')).toBeVisible();
}

test('detail modal opens on Overview tab with summary header + action footer', async ({ page }) => {
  await openDetailModal(page);
  await expect(page.locator('[data-testid="tab-overview"]')).toHaveAttribute('aria-selected', 'true');
  await expect(page.locator('[data-testid="panel-overview"]')).toBeVisible();
  await expect(page.locator('[data-testid="detail-summary-chips"]')).toBeVisible();
  await expect(page.locator('[data-testid="detail-actions"]')).toBeVisible();
});

test('each visible tab reveals its own panel; summary header + footer persist', async ({ page }) => {
  await openDetailModal(page);

  const tabButtons = page.locator('[role="tab"]');
  const count = await tabButtons.count();
  expect(count).toBeGreaterThanOrEqual(1); // Overview always present

  for (let i = 0; i < count; i++) {
    const btn = tabButtons.nth(i);
    const key = (await btn.getAttribute('data-testid'))!.replace('tab-', '');
    await btn.click();
    // Only the active panel is mounted → its panel is visible.
    await expect(page.locator(`[data-testid="panel-${key}"]`)).toBeVisible();
    await expect(btn).toHaveAttribute('aria-selected', 'true');
    // Context never lost when switching tabs.
    await expect(page.locator('[data-testid="detail-summary-chips"]')).toBeVisible();
    await expect(page.locator('[data-testid="detail-actions"]')).toBeVisible();
  }
});

test('empty tabs are not rendered (only known keys appear)', async ({ page }) => {
  await openDetailModal(page);
  const keys = await page.locator('[role="tab"]').evaluateAll((els) =>
    els.map((e) => e.getAttribute('data-testid')?.replace('tab-', ''))
  );
  const allowed = new Set(['overview', 'financing', 'investment', 'area']);
  for (const k of keys) {
    expect(allowed.has(k!), `unexpected tab: ${k}`).toBe(true);
  }
  // No duplicate tabs.
  expect(new Set(keys).size).toBe(keys.length);
});
