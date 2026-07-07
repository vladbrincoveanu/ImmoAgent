import { test, expect } from '@playwright/test';
import { MongoClient } from 'mongodb';

// Profiles consolidated 10 → 5 on 2026-07-06; only `default` is free.
// Anonymous visitors are free tier, so switching to a persona must paywall.

test('profile selector is visible on dashboard', async ({ page }) => {
  await page.goto('/dashboard');
  await page.waitForLoadState('networkidle');
  const selector = page.locator('[data-testid="profile-selector"]');
  await expect(selector).toBeVisible();
  await expect(selector).toHaveValue('default');
});

test('free user switching to a Pro persona shows paywall and reverts to default', async ({ page }) => {
  await page.goto('/dashboard');
  await page.waitForLoadState('networkidle');
  await page.selectOption('[data-testid="profile-selector"]', 'growing_family');
  await expect(page.locator('[data-testid="paywall-modal"]')).toBeVisible();
  await page.locator('[data-testid="paywall-modal"] button:has-text("Not now")').click();
  await expect(page.locator('[data-testid="profile-selector"]')).toHaveValue('default');
  await expect(page).not.toHaveURL(/profile=/);
});

test('legacy alias owner_occupier in URL normalizes to default without paywall', async ({ page }) => {
  await page.goto('/dashboard?profile=owner_occupier');
  await page.waitForLoadState('networkidle');
  await expect(page.locator('[data-testid="profile-selector"]')).toHaveValue('default');
  await expect(page.locator('[data-testid="paywall-modal"]')).not.toBeVisible();
});

test('invalid profile in URL falls back to default', async ({ page }) => {
  await page.goto('/dashboard?profile=garbage');
  await page.waitForLoadState('networkidle');
  await expect(page.locator('[data-testid="profile-selector"]')).toHaveValue('default');
});

// Pro entitlement path — needs direct DB access to seed is_pro, so it only
// runs against the local server (localhost Mongo). Skipped on prod runs.
test('pro user: profile switch updates URL and persists across refresh', async ({ page, baseURL, context }) => {
  test.skip(!baseURL?.includes('localhost'), 'requires local Mongo to seed a pro user');
  const proId = `u_profiletest${Date.now().toString(16)}`;
  const client = new MongoClient('mongodb://localhost:27017/immo');
  await client.connect();
  await client.db('immo').collection('users').updateOne(
    { _id: proId as never },
    { $set: { is_pro: true } },
    { upsert: true },
  );
  await client.close();
  await context.addCookies([{ name: 'immo_user', value: proId, url: baseURL! }]);

  await page.goto('/dashboard');
  await page.waitForLoadState('networkidle');
  await page.selectOption('[data-testid="profile-selector"]', 'urban_professional');
  await page.waitForURL(/profile=urban_professional/);
  await expect(page.locator('[data-testid="paywall-modal"]')).not.toBeVisible();
  await page.reload();
  await expect(page).toHaveURL(/profile=urban_professional/);
  await expect(page.locator('[data-testid="profile-selector"]')).toHaveValue('urban_professional');
});
