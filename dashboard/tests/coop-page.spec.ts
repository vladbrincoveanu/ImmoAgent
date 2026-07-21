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

    // Exactly the two builder-direct co-op units. Both excluded controls: the
    // non-coop purchase listing AND the mis-tagged Willhaben "co-op" (coop_source
    // = willhaben) — /coop is builder-direct only.
    const items = page.getByTestId('coop-item');
    await expect(items).toHaveCount(2);
    await expect(page.getByTestId('coop-count')).toHaveText('2 Treffer');
    await expect(page.locator('body')).not.toContainText('450.000');
    await expect(page.locator('body')).not.toContainText('WILLHABEN-COOP-CONTROL');

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

    // The 1130 unit has a resolved builder_url → links to the builder's own
    // reservation page, NOT to mygewo and NOT to willhaben.
    const firstHref = await first.getByRole('link').first().getAttribute('href');
    expect(firstHref).toBe('https://www.oevw.at/suche/6127-leopoldauer-strasse-157a-2-23');
    expect(firstHref).not.toContain('mygewo.at');
    expect(firstHref).not.toContain('willhaben');

    // The 1220 unit has no builder_url → falls back to the mygewo offer page.
    const secondHref = await second.getByRole('link').first().getAttribute('href');
    expect(secondHref).toContain('mygewo.at/genossenschaftswohnungen/angebot/');

    expect(errors).toHaveLength(0);
  });

  test('nav header exposes the Genossenschaft link', async ({ page }) => {
    await page.goto('/dashboard');
    const link = page.getByRole('link', { name: 'Genossenschaft' });
    await expect(link).toHaveAttribute('href', '/coop');
  });
});
