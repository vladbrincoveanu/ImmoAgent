import { test, expect } from '@playwright/test';

/**
 * /dashboard/map renders two full trees: `hidden md:flex` (desktop) and
 * `md:hidden` (mobile). Tailwind's `hidden` is display:none — it hides but does
 * NOT unmount — so both trees used to mount their own Leaflet map on every
 * load. At 1440x900 the invisible mobile map carried 197 markers (the full set)
 * while the visible desktop map carried 89 (viewport-culled): the hidden map
 * was doing more work than the real one.
 *
 * These tests fail if the second map comes back.
 */

async function mapReady(page: import('@playwright/test').Page) {
  await page.goto('/dashboard/map');
  await expect(page.locator('.leaflet-container').first()).toBeVisible({ timeout: 30000 });
  // Let the other branch mount too, if it (incorrectly) still would.
  await page.waitForTimeout(2500);
}

test.describe('Map mounts exactly once per viewport', () => {
  test('desktop viewport mounts a single Leaflet instance', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await mapReady(page);

    await expect(page.locator('.leaflet-container')).toHaveCount(1);

    // The one that mounted must be the visible desktop one, not the 0x0 mobile one.
    const box = await page.locator('.leaflet-container').boundingBox();
    expect(box).not.toBeNull();
    expect(box!.width).toBeGreaterThan(300);
    expect(box!.height).toBeGreaterThan(300);
  });

  test('mobile viewport mounts a single Leaflet instance', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await mapReady(page);

    await expect(page.locator('.leaflet-container')).toHaveCount(1);

    const box = await page.locator('.leaflet-container').boundingBox();
    expect(box).not.toBeNull();
    expect(box!.width).toBeGreaterThan(200);
  });

  test('profile selector is unambiguous on desktop', async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 900 });
    await mapReady(page);

    // Previously resolved to 2 elements (one per tree) and tripped strict mode.
    // Both trees still render their chrome, so scope to the visible one.
    const visible = page.locator('[data-testid="profile-selector"]:visible');
    await expect(visible).toHaveCount(1);
  });
});
