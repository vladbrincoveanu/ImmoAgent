import { test, expect } from '@playwright/test';

// Verifies /coop renders co-op RENTALS (which the purchase-tuned map view
// filters out) against seeded local Mongo. Asserts real DOM, not screenshots.
test.describe('/coop co-op listings page', () => {
  test('renders only co-op units with full details, no console errors', async ({ page }) => {
    const errors: string[] = [];
    page.on('console', (m) => {
      if (m.type() === 'error') errors.push(m.text());
    });

    await page.goto('/coop');

    // Page + heading present
    await expect(page.getByRole('heading', { name: 'Genossenschaftswohnungen' })).toBeVisible();

    // Exactly the two seeded co-op units (the willhaben purchase control is excluded)
    const items = page.getByTestId('coop-item');
    await expect(items).toHaveCount(2);
    await expect(page.getByTestId('coop-count')).toHaveText('2 Treffer');
    await expect(page.locator('body')).not.toContainText('450.000');

    // Newest first: 1130 OEVW (processed 1h ago) before 1220 OESW (3 days ago)
    const first = items.nth(0);
    await expect(first.getByTestId('coop-address')).toContainText('Thomas-Morus-Gasse 2-12');
    await expect(first.getByTestId('coop-district')).toHaveText('1130');
    await expect(first.getByTestId('coop-rooms')).toHaveText('3 Zimmer');
    await expect(first.getByTestId('coop-rent')).toContainText('€550');
    await expect(first.getByTestId('coop-buyoption')).toHaveText('Kaufoption');
    await expect(first.getByTestId('coop-dev')).toHaveText('OEVW');

    const second = items.nth(1);
    await expect(second.getByTestId('coop-address')).toContainText('Erzherzog-Karl-Straße 140');
    await expect(second.getByTestId('coop-district')).toHaveText('1220');
    await expect(second.getByTestId('coop-rent')).toContainText('€945');
    await expect(second.getByTestId('coop-area')).toContainText('70');
    // 1220 unit has no buy option
    await expect(second.getByTestId('coop-buyoption')).toHaveCount(0);

    // Each card links out to the mygewo offer page
    const href = await first.getByRole('link').first().getAttribute('href');
    expect(href).toContain('mygewo.at/genossenschaftswohnungen/angebot/');

    expect(errors).toHaveLength(0);
  });

  test('nav header exposes the Genossenschaft link', async ({ page }) => {
    await page.goto('/dashboard');
    const link = page.getByRole('link', { name: 'Genossenschaft' });
    await expect(link).toHaveAttribute('href', '/coop');
  });
});
