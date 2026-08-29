# Co-op Availability UI Filtering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep unavailable co-op records in MongoDB for statistics while excluding them from both active co-op feeds and detecting builder-offer URLs that return 404/410.

**Architecture:** Put the active-status predicate in the two shared co-op Mongo query builders, which covers the list pages and the co-op map path. Make revalidation probe `builder_url` when it exists, but mark the canonical stored `url` as taken so existing history and statistics remain keyed consistently.

**Tech Stack:** Next.js 15, React, TypeScript, MongoDB, Playwright, Python, pytest, graphify.

---

## File Map

- Create: `dashboard/tests/coop-availability.spec.ts` - browser regression with isolated active/taken fixtures for both co-op feeds.
- Modify: `dashboard/lib/coop-query.ts` - shared active co-op query predicates.
- Modify: `Project/Application/cleanup.py` - builder URL probe selection.
- Modify: `tests/test_taken_listings.py` - canonical URL versus builder URL regression.
- Create: `.frontend-design/baselines/coop-availability-*.png` - viewport captures required by the UI verification rule.
- Create: `.frontend-design/baselines/before/coop-availability-*.png` - pre-change comparison captures.
- Update: `graphify-out/` generated graph artifacts after implementation.

## Task 1: Add Failing Regression Tests

**Files:**
- Create: `dashboard/tests/coop-availability.spec.ts`
- Modify: `tests/test_taken_listings.py`

- [ ] **Step 1: Add the browser regression fixture and assertions**

Create `dashboard/tests/coop-availability.spec.ts` with fixtures that cannot
collide with scraped data:

```ts
import { test, expect } from '@playwright/test';
import { MongoClient } from 'mongodb';

const URI = process.env.MONGODB_URI || 'mongodb://localhost:27017/immo';
const FIXTURE_PREFIX = 'https://fixture.invalid/coop-availability/';

function doc(suffix: string, extra: Record<string, unknown> = {}) {
  return {
    url: FIXTURE_PREFIX + suffix,
    title: `Availability fixture ${suffix}`,
    address: `Availabilitygasse ${suffix}, 1220 Wien`,
    bezirk: '1220',
    rooms: 3,
    area_m2: 80,
    price_total: 900,
    own_funds: 10000,
    bautraeger: 'FixtureBau',
    builder_url: FIXTURE_PREFIX + 'builder/' + suffix,
    image_url: null,
    special_features: [],
    is_genossenschaft: true,
    buyable: false,
    coop_source: 'bautraeger_direct',
    url_is_valid: true,
    listing_status: 'active',
    processed_at: Math.floor(Date.now() / 1000),
    ...extra,
  };
}

let client: MongoClient;

test.beforeAll(async () => {
  client = new MongoClient(URI);
  await client.connect();
  const listings = client.db('immo').collection('listings');
  await listings.deleteMany({ url: { $regex: '^' + FIXTURE_PREFIX } });
  await listings.insertMany([
    doc('developer-active'),
    doc('developer-taken', { listing_status: 'taken' }),
    doc('private-active', {
      coop_kind: 'private_transfer',
      coop_source: 'willhaben',
      description: 'Active private transfer',
    }),
    doc('private-taken', {
      coop_kind: 'private_transfer',
      coop_source: 'willhaben',
      description: 'Taken private transfer',
      listing_status: 'taken',
    }),
  ]);
});

test.afterAll(async () => {
  await client.db('immo').collection('listings')
    .deleteMany({ url: { $regex: '^' + FIXTURE_PREFIX } });
  await client.close();
});

test('/coop hides taken developer offers but keeps active offers', async ({ page }) => {
  await page.goto('/coop');

  await expect(page.getByTestId('coop-item')).toHaveCount(1);
  await expect(page.getByTestId('coop-address')).toContainText('developer-active');
  await expect(page.locator('body')).not.toContainText('developer-taken');
});

test('/coop/private hides taken private transfers but keeps active transfers', async ({ page }) => {
  await page.goto('/coop/private');

  await expect(page.getByTestId('private-item')).toHaveCount(1);
  await expect(page.getByTestId('private-title')).toContainText('private-active');
  await expect(page.locator('body')).not.toContainText('private-taken');
});
```

- [ ] **Step 2: Add the builder URL revalidation regression**

Append this test to `tests/test_taken_listings.py`:

```python
def test_mark_taken_listings_probes_builder_url_but_marks_canonical_url():
    """Builder-offer removal marks the stored MyGEWO record as taken."""
    from Application.cleanup import mark_taken_listings
    from unittest.mock import MagicMock, patch

    canonical_url = 'https://mygewo.at/genossenschaftswohnungen/angebot/unit'
    builder_url = 'https://builder.example/offers/unit'
    mock_mongo = MagicMock()
    mock_mongo.collection = MagicMock()
    mock_mongo.collection.find.return_value = [{
        '_id': 3,
        'url': canonical_url,
        'builder_url': builder_url,
        'source_enum': 'genossenschaft',
    }]
    mock_mongo.mark_listing_taken = MagicMock(return_value=True)

    with patch('Application.cleanup.requests.head') as mock_head:
        mock_head.return_value = MagicMock(status_code=410)
        result = mark_taken_listings(
            mock_mongo,
            source_filter=['genossenschaft'],
        )

    assert result['newly_taken'] == 1
    assert mock_head.call_args.args[0] == builder_url
    mock_mongo.mark_listing_taken.assert_called_once_with(canonical_url)
```

- [ ] **Step 3: Run the browser regression and confirm it fails for the missing filter**

Run from `dashboard/`:

```bash
npx playwright test tests/coop-availability.spec.ts --reporter=line
```

Expected: the two tests fail because the current queries return both the active
and `listing_status: "taken"` fixtures. The failure must be an item-count
mismatch, not a MongoDB connection or build error.

- [ ] **Step 4: Run the revalidation regression and confirm it fails for the wrong probe URL**

Run from the repository root:

```bash
pytest tests/test_taken_listings.py::test_mark_taken_listings_probes_builder_url_but_marks_canonical_url -q
```

Expected: FAIL because the current implementation passes `canonical_url` to
`requests.head` instead of `builder_url`. Do not change production code before
both red signals are observed.

- [ ] **Step 5: Commit the red tests**

```bash
git add dashboard/tests/coop-availability.spec.ts tests/test_taken_listings.py
git commit -m "test: reproduce stale co-op rows"
```

## Task 2: Filter Taken Co-ops at the Shared Query Boundary

**Files:**
- Modify: `dashboard/lib/coop-query.ts:40-59`
- Test: `dashboard/tests/coop-availability.spec.ts`

- [ ] **Step 1: Add the active-status predicate to both query builders**

Add this field to the object returned by `privateCoopQuery()` and the object
returned by `coopBaseQuery()`:

```ts
listing_status: { $ne: 'taken' },
```

Keep `url_is_valid`, Vienna district, source, rental, and area predicates
unchanged. MongoDB's `$ne` matches missing and null fields, preserving the
existing backward-compatible interpretation of legacy rows as active.

- [ ] **Step 2: Run the browser regression and confirm it passes**

```bash
npx playwright test tests/coop-availability.spec.ts --reporter=line
```

Expected: 2 passed, 0 failed. The browser must render one active developer
offer and one active private transfer, with neither taken marker in the DOM.

- [ ] **Step 3: Commit the query fix**

```bash
git add dashboard/lib/coop-query.ts
git commit -m "fix: hide taken co-op rows"
```

## Task 3: Probe the URL Users Actually Open

**Files:**
- Modify: `Project/Application/cleanup.py:388-407`
- Test: `tests/test_taken_listings.py`

- [ ] **Step 1: Include `builder_url` in the revalidation projection and select the probe target**

Change the projection to include `builder_url`, then use the builder URL when
present:

```python
cursor = mongo_handler.collection.find(
    query,
    {"url": 1, "builder_url": 1, "source_enum": 1, "_id": 1},
)
listings = list(cursor)

for idx, doc in enumerate(listings):
    url = doc.get('url')
    probe_url = doc.get('builder_url') or url
    source = doc.get('source_enum')
    if not url or not probe_url:
        continue

    stats["checked"] += 1
    url_invalid = False

    try:
        resp = requests.head(
            probe_url,
            headers=DEFAULT_HEADERS,
            allow_redirects=True,
            timeout=timeout,
        )
```

Leave the rest of the status handling unchanged, including passing `url` to
`mongo_handler.mark_listing_taken(url)`. This retains the canonical record and
prevents a builder URL from becoming a new Mongo identity.

- [ ] **Step 2: Run the focused Python tests**

```bash
pytest tests/test_taken_listings.py -q
```

Expected: all tests in this file pass, including the new builder URL test and
the existing daily revalidation tests.

- [ ] **Step 3: Commit the revalidation fix**

```bash
git add Project/Application/cleanup.py tests/test_taken_listings.py
git commit -m "fix: revalidate co-op builder URLs"
```

## Task 4: Visual Verification

**Files:**
- Create: `.frontend-design/baselines/coop-availability-375.png`
- Create: `.frontend-design/baselines/coop-availability-768.png`
- Create: `.frontend-design/baselines/coop-availability-1280.png`

- [ ] **Step 1: Start the production dashboard server**

Use the existing Playwright production-server contract from
`dashboard/playwright.config.ts`:

```bash
npm run build
MONGODB_URI=mongodb://localhost:27017/immo PORT=3010 npm run start
```

- [ ] **Step 2: Capture the changed page at all required viewports**

From the repository root, use a one-off Playwright script through Node. It
must assert the page loaded and write only the three requested captures:

```bash
node - <<'NODE'
const { chromium } = require('./dashboard/node_modules/playwright');

(async () => {
  const fs = require('node:fs');
  fs.mkdirSync('.frontend-design/baselines', { recursive: true });
  const browser = await chromium.launch();
  for (const width of [375, 768, 1280]) {
    const page = await browser.newPage({ viewport: { width, height: 900 } });
    await page.goto('http://localhost:3010/coop', { waitUntil: 'networkidle' });
    await page.getByTestId('coop-page').waitFor();
    await page.screenshot({
      path: `.frontend-design/baselines/coop-availability-${width}.png`,
      fullPage: true,
    });
    await page.close();
  }
  await browser.close();
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
NODE
```

- [ ] **Step 3: Compare against the pre-change captures**

Before Task 2 changes the query, use the same capture script with the output
directory `.frontend-design/baselines/before/` and create that directory first.
After the fix, compare each corresponding viewport with the Playwright visual
comparison command below. The expected visual difference is removal of
unavailable rows only; there must be no layout overflow, broken navigation, or
mobile wrapping regression:

```bash
node - <<'NODE'
const { chromium } = require('./dashboard/node_modules/playwright');
const fs = require('node:fs');

(async () => {
  const browser = await chromium.launch();
  for (const width of [375, 768, 1280]) {
    const page = await browser.newPage({ viewport: { width, height: 900 } });
    await page.goto('http://localhost:3010/coop', { waitUntil: 'networkidle' });
    await page.getByTestId('coop-page').waitFor();
    fs.mkdirSync('.frontend-design/baselines/before', { recursive: true });
    await page.screenshot({
      path: `.frontend-design/baselines/after-${width}.png`,
      fullPage: true,
    });
    await page.close();
  }
  await browser.close();
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
NODE
```

Use `npx playwright test --update-snapshots` only when the changed pixels are
the intentional removal of taken rows. Keep both before and after captures in
`.frontend-design/baselines/` for review.

- [ ] **Step 4: Stop the server**

```bash
pkill -f "next start"
```

## Task 5: Full Verification and Graph Refresh

- [ ] **Step 1: Run dashboard unit tests**

```bash
cd dashboard
npm test -- --runInBand
```

Expected: 8 suites and 79 baseline tests, plus any newly added unit coverage,
pass with no failures.

- [ ] **Step 2: Run the full dashboard browser suite**

```bash
npx playwright test --reporter=line
```

Expected: 0 failures and no unexpected console errors. Existing tests that
depend on local seeded data must either pass against their own fixtures or be
reported as pre-existing environment failures; do not hide new failures.

- [ ] **Step 3: Run Python regressions**

From the repository root:

```bash
pytest -q
```

Expected: all Python tests pass, including the co-op and taken-listing suites.

- [ ] **Step 4: Refresh the code graph**

From the repository root:

```bash
graphify update .
```

Confirm the graph contains the changed query and cleanup modules. Do not add
hand-written graph edges; generated graph artifacts must reflect source code.

- [ ] **Step 5: Inspect the final diff and status**

```bash
git status --short
git diff --check
git diff HEAD~3..HEAD -- dashboard/lib/coop-query.ts Project/Application/cleanup.py dashboard/tests/coop-availability.spec.ts tests/test_taken_listings.py
```

Confirm only the spec, plan, intended implementation/tests, visual captures,
and graph refresh artifacts are present. Confirm no credentials or local
environment files are staged.

- [ ] **Step 6: Create the final fix commit if graph or visual artifacts remain uncommitted**

```bash
git add dashboard/lib/coop-query.ts Project/Application/cleanup.py dashboard/tests/coop-availability.spec.ts tests/test_taken_listings.py .frontend-design/baselines graphify-out
git commit -m "fix: remove unavailable co-ops from UI"
```

Do not amend earlier commits. If all implementation files are already committed
and only generated verification artifacts changed, use this commit only for
those intended artifacts.

## Task 6: Merge into `main` and Push

- [ ] **Step 1: Re-verify repository ownership and remote**

```bash
git remote -v
```

Expected remote: `https://github.com/vladbrincoveanu/ImmoAgent.git`. Stop before
pushing if the remote differs.

- [ ] **Step 2: Create an isolated main worktree and fast-forward it**

Run from the repository root checkout, not by switching branches in the feature
worktree:

```bash
git worktree add .worktrees/main-push main
git -C .worktrees/main-push merge --ff-only bugfix/coop-availability-filter
```

If `main` is not an ancestor of the feature branch, stop and report the commit
divergence instead of creating an implicit merge commit.

- [ ] **Step 3: Verify the main worktree before pushing**

```bash
git -C .worktrees/main-push status --short --branch
```

Expected: clean `main` worktree with the co-op availability commits at its tip.

- [ ] **Step 4: Push `main`**

```bash
git -C .worktrees/main-push push origin main
```

Report the pushed commit SHA and the verification results. Do not force-push.
