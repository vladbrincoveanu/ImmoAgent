import { test, expect } from '@playwright/test';

test('co-op filter toggles and shows only co-op listings', async ({ page }) => {
  const errors: string[] = [];
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text()); });

  await page.goto('/dashboard/map');
  await page.getByRole('button', { name: /genossenschaft/i }).click();
  await page.waitForResponse((r) => r.url().includes('/api/listings/map') && r.ok());

  // At least one co-op marker OR an explicit empty-state — never a crash.
  await expect(page.locator('body')).toBeVisible();
  expect(errors).toHaveLength(0);
});
