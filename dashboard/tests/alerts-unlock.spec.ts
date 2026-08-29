import { test, expect } from '@playwright/test';

/** The password unlock that used to gate /alerts, asserted absent.
 *
 * The gate was removed on both sides: no unlock box on the page, and the create
 * route no longer answers 402. These tests are the regression guard — the gate
 * cost the owner a round trip through a shared secret in every new browser, and
 * re-introducing it silently would look exactly like an alert that never fires.
 *
 * The file keeps its name so the history of the feature stays in one place. */

const ME_API = '**/api/me';
const ALERT_API = '**/api/saved-searches/alert';

/** Keep the alert list quiet so these tests only exercise the gate. */
async function stubAlerts(page: import('@playwright/test').Page) {
  await page.route(ALERT_API, (route) =>
    route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ items: [] }),
    }));
}

test('a free user gets the create form, not an unlock box', async ({ page }) => {
  await stubAlerts(page);
  await page.route(ME_API, (route) =>
    route.fulfill({
      status: 200, contentType: 'application/json',
      body: JSON.stringify({ is_pro: false, saved_search_count: 0 }),
    }));

  await page.goto('/alerts');
  await expect(page.getByTestId('alert-form')).toBeVisible();
  await expect(page.getByTestId('unlock-form')).toHaveCount(0);
  await expect(page.getByTestId('unlock-password')).toHaveCount(0);
});

/** The page must not depend on /api/me at all any more. A deployment where that
 * route is broken used to hide the form behind a permanent unlock box. */
test('the form works even when the entitlement route is down', async ({ page }) => {
  await stubAlerts(page);
  await page.route(ME_API, (route) => route.fulfill({ status: 500, body: '' }));

  await page.goto('/alerts');
  await expect(page.getByTestId('alert-form')).toBeVisible();
  await expect(page.getByTestId('alert-submit')).toBeEnabled();
});

/** Hits the real route with no cookie and no entitlement. A 402 here means the
 * server-side gate came back. Any other refusal (400 for the missing channel,
 * 503 with no database) is fine — this asserts one specific status is absent. */
test('the real create endpoint no longer answers 402', async ({ request }) => {
  const res = await request.post('/api/saved-searches/alert', {
    data: { kind: 'coop_private', keywords: ['Genossenschaft'],
            telegram_chat_id: '-100123456' },
  });
  expect(res.status()).not.toBe(402);
});

test('the keyword field defaults to every builder-direct MyGEWO unit', async ({ page }) => {
  await stubAlerts(page);
  await page.goto('/alerts');
  const keywords = page.getByTestId('alert-keywords');
  await expect(keywords).toHaveValue('');
  await expect(page.getByTestId('alert-private-only')).not.toBeChecked();
});

test('the all-MyGEWO feed is the default and can be submitted directly',
  async ({ page }) => {
    let posted: { kind?: string } | null = null;
    await page.route(ALERT_API, (route) => {
      if (route.request().method() === 'POST') {
        posted = route.request().postDataJSON();
        return route.fulfill({
          status: 201, contentType: 'application/json',
          body: JSON.stringify({ ok: true, message: 'Alert created.' }),
        });
      }
      return route.fulfill({
        status: 200, contentType: 'application/json',
        body: JSON.stringify({ items: [] }),
      });
    });

    await page.goto('/alerts');
    await expect(page.getByTestId('alert-private-only')).not.toBeChecked();

    await page.getByTestId('alert-chatid').fill('-100123456');
    await page.getByTestId('alert-submit').click();

    // Unchecked means all builder-direct MyGEWO rentals; checking the box opts
    // into the separate private-handover rubric.
    await expect.poll(() => posted?.kind).toBe('mygewo');
  });
