import { test, expect } from '@playwright/test';
import { MongoClient } from 'mongodb';

// Freemium gate: free tier = 3 saved searches, alerts Pro-only.
// Each test uses a fresh browser context → fresh immo_user cookie → clean quota.

test.describe('freemium gate', () => {
  test('saved searches: 3 free, 4th returns 402', async ({ page }) => {
    await page.goto('/dashboard');
    for (let i = 1; i <= 3; i++) {
      const res = await page.request.post('/api/saved-searches', {
        data: { name: `gate test ${i}`, params: { minScore: '10' } },
      });
      expect(res.status(), `save #${i} should succeed`).toBe(201);
    }
    const fourth = await page.request.post('/api/saved-searches', {
      data: { name: 'gate test 4', params: {} },
    });
    expect(fourth.status()).toBe(402);
    const body = await fourth.json();
    expect(body.reason).toBe('saved_search_limit');
    expect(body.limit).toBe(3);
  });

  test('save-search UI shows paywall modal at limit', async ({ page }) => {
    await page.goto('/dashboard');
    for (let i = 1; i <= 3; i++) {
      const res = await page.request.post('/api/saved-searches', {
        data: { name: `ui gate ${i}`, params: {} },
      });
      expect(res.status()).toBe(201);
    }
    page.on('dialog', (d) => d.accept('one too many'));
    await page.getByTestId('save-search-btn').click();
    await expect(page.getByTestId('paywall-modal')).toBeVisible();
    await page.getByTestId('paywall-email').fill('gate-test@example.com');
    await page.getByTestId('paywall-submit').click();
    await expect(page.getByTestId('paywall-success')).toBeVisible();
  });

  test('alerts are Pro-only: API returns 402, modal shows upgrade flow', async ({ page }) => {
    await page.goto('/dashboard');
    const res = await page.request.post('/api/saved-searches/alert', {
      data: { email: 'gate-test@example.com', params: {}, frequency: 'daily' },
    });
    expect(res.status()).toBe(402);
    expect((await res.json()).reason).toBe('alerts_pro_only');

    await page.getByTestId('open-alerts').click();
    await expect(page.getByTestId('email-alerts-modal')).toBeVisible();
    await page.getByTestId('alerts-email').fill('gate-test@example.com');
    await page.getByTestId('alerts-submit').click();
    await expect(page.getByTestId('alerts-paywall')).toBeVisible();
    await page.getByTestId('alerts-paywall-submit').click();
    await expect(page.getByTestId('alerts-paywall-success')).toBeVisible();
  });

  test('/api/me reports free tier and quota', async ({ page }) => {
    await page.goto('/dashboard');
    const created = await page.request.post('/api/saved-searches', {
      data: { name: 'me test', params: {} },
    });
    expect(created.status()).toBe(201);
    const me = await page.request.get('/api/me');
    expect(me.status()).toBe(200);
    const body = await me.json();
    expect(body.is_pro).toBe(false);
    expect(body.saved_search_count).toBe(1);
    expect(body.saved_search_limit).toBe(3);
  });

  test('persona profiles are Pro-only: API returns 402 with pro_profiles reason', async ({ page }) => {
    await page.goto('/dashboard');
    for (const profile of ['growing_family', 'budget_buyer', 'diy_renovator', 'urban_professional']) {
      const res = await page.request.get(`/api/listings/top?profile=${profile}`);
      expect(res.status(), `profile=${profile}`).toBe(402);
      expect((await res.json()).reason).toBe('pro_profiles');
    }
    const map = await page.request.get('/api/listings/map?profile=growing_family');
    expect(map.status()).toBe(402);
    const insights = await page.request.get('/api/insights?profile=growing_family');
    expect(insights.status()).toBe(402);
  });

  test('default and legacy-alias-to-default profiles stay free, scores map is stripped', async ({ page }) => {
    await page.goto('/dashboard');
    const plain = await page.request.get('/api/listings/top');
    expect(plain.status()).toBe(200);
    // owner_occupier + retiree were consolidated into default → still free
    for (const legacy of ['owner_occupier', 'retiree']) {
      const res = await page.request.get(`/api/listings/top?profile=${legacy}`);
      expect(res.status(), `legacy profile=${legacy}`).toBe(200);
    }
    // Free tier must not receive the full per-persona scores map (the client
    // could re-sort locally from it, bypassing the gate)
    const body = await plain.json();
    for (const l of body.listings ?? []) expect(l.scores).toBeNull();
  });

  // Pro entitlement path — needs direct DB access to seed is_pro, so it only
  // runs against the local server (localhost Mongo). Skipped on prod runs.
  test('pro user: unlimited saves and alerts allowed', async ({ page, baseURL, context }) => {
    test.skip(!baseURL?.includes('localhost'), 'requires local Mongo to seed a pro user');
    const proId = `u_protest${Date.now().toString(16)}`;
    const client = new MongoClient('mongodb://localhost:27017/immo');
    await client.connect();
    await client.db('immo').collection('users').updateOne(
      { _id: proId as never },
      { $set: { is_pro: true }, $setOnInsert: { created_at: new Date() } },
      { upsert: true },
    );
    await client.close();
    await context.addCookies([{ name: 'immo_user', value: proId, url: baseURL! }]);

    await page.goto('/dashboard');
    for (let i = 1; i <= 4; i++) {
      const res = await page.request.post('/api/saved-searches', {
        data: { name: `pro save ${i}`, params: {} },
      });
      expect(res.status(), `pro save #${i}`).toBe(201);
    }
    const me = await page.request.get('/api/me');
    expect((await me.json()).is_pro).toBe(true);
    const alert = await page.request.post('/api/saved-searches/alert', {
      data: { email: 'pro-test@example.com', params: {}, frequency: 'daily' },
    });
    expect(alert.status()).toBe(201);

    // Persona profiles unlocked for pro
    const top = await page.request.get('/api/listings/top?profile=growing_family');
    expect(top.status()).toBe(200);
  });
});
