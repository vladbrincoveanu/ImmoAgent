# All MyGEWO Co-op Alerts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let users subscribe to every new builder-direct MyGEWO co-op rental without widening the alert to ordinary Willhaben listings or changing private-handover behavior.

**Architecture:** Add an explicit `mygewo` subscription kind. The shared matcher treats that kind as a source boundary (`coop_source == "bautraeger_direct"`), then applies its existing optional keyword and numeric gates. The dashboard uses `mygewo` for its default all-co-op mode and keeps `coop_private` as an explicit private-tenant-handover mode; broadcast channel filtering remains unchanged.

**Tech Stack:** Python, pytest, MongoDB/PyMongo, Next.js 15, TypeScript, Jest, Playwright.

---

## Current Context

- Worktree: `/Users/vladbrincoveanu/.config/superpowers/worktrees/immo-scouter/cleanup-alerts-2026-08-28`.
- The worktree already contains the uncommitted legacy compatibility fix: `USER_ALERT_KINDS` includes `None`, and the pre-kind email-only regression passes.
- MyGEWO listings produced by `genossenschaft_scraper.py` carry `coop_source = "bautraeger_direct"` and do not carry `coop_kind = "private_transfer"`.
- `coop_private` must continue requiring `coop_kind = "private_transfer"`.
- Existing `CHANNEL_ALERT_KINDS = ["coop_private", "keyword"]` must remain unchanged.
- The current `/alerts` form defaults to `coop_private` and prefilled marker keywords. The new default must be all MyGEWO with an empty keyword field.

## File Map

- Modify `Project/Application/alert_matcher.py` to add the source-scoped `mygewo` rubric.
- Modify `Project/run_coop.py` to query `mygewo` user subscriptions while preserving the channel kind list and the legacy `None` sentinel.
- Modify `Project/Tests/test_alert_matcher.py` with positive and negative source-boundary tests.
- Modify `Project/Tests/test_run_coop.py` with a Telegram delivery regression and updated kind-list expectations.
- Modify `Project/Tests/test_coop_channel_ledger.py` with a broadcast-isolation regression.
- Modify `dashboard/app/api/saved-searches/alert/route.ts` to accept and document `mygewo`.
- Create `dashboard/app/api/saved-searches/alert/route.test.ts` to test API acceptance and rejection of alert kinds.
- Modify `dashboard/app/alerts/page.tsx` to make all MyGEWO the default feed and retain private handovers as an opt-in.
- Modify `dashboard/tests/alerts-page.spec.ts` to cover the new default and private opt-in.

### Task 1: Add the failing MyGEWO matcher tests

**Files:**
- Modify: `Project/Tests/test_alert_matcher.py:110-125`

- [ ] **Step 1: Extend the listing stub with source metadata**

Add `coop_source=None` to `_LN.__init__` and assign it to `self.coop_source`, leaving all existing constructor arguments and assertions intact:

```python
    def __init__(self, title=None, description=None,
                 area_m2=None, rooms=None, price_total=None, coop_kind=None,
                 coop_source=None):
        self.title = title
        self.address = None
        self.bezirk = None
        self.description = description
        self.area_m2 = area_m2
        self.rooms = rooms
        self.price_total = price_total
        self.coop_kind = coop_kind
        self.coop_source = coop_source
```

- [ ] **Step 2: Write source-boundary regression tests**

Append these tests after the existing `test_other_kinds_see_the_whole_feed` test:

```python
def test_mygewo_matches_builder_direct_listing_without_keywords():
    alert = _alert(kind="mygewo", keywords=[])
    listing = _LN(
        title="1100 Wien - 3 Zimmer",
        coop_source="bautraeger_direct",
    )

    assert alert_matches(alert, listing) is True


def test_mygewo_rejects_non_builder_direct_listing():
    alert = _alert(kind="mygewo", keywords=[])

    assert alert_matches(alert, _LN(coop_source="willhaben")) is False
    assert alert_matches(alert, _LN(coop_source=None)) is False
```

- [ ] **Step 3: Run the new matcher test and verify it fails for the missing rubric**

Run from `Project/`:

```bash
pytest Tests/test_alert_matcher.py::test_mygewo_rejects_non_builder_direct_listing -q
```

Expected result: `FAIL`, because the current `rubric_hit()` treats every kind other than `coop_private` as unrestricted.

### Task 2: Implement the Python matcher and user-alert query

**Files:**
- Modify: `Project/Application/alert_matcher.py:81-96`
- Modify: `Project/run_coop.py:53-60`
- Test: `Project/Tests/test_alert_matcher.py`
- Test: `Project/Tests/test_run_coop.py:658-674`

- [ ] **Step 1: Add the minimal `mygewo` rubric after the private rubric check**

Update `rubric_hit()` so the source-scoped kind fails closed before the existing private-transfer branch:

```python
    if alert.get("kind") == "mygewo":
        return getattr(listing, "coop_source", None) == "bautraeger_direct"
    if alert.get("kind") != "coop_private":
        return True
    return getattr(listing, "coop_kind", None) == "private_transfer"
```

Do not change `keyword_hit()`, `gate_result()`, or the `coop_private` branch.

- [ ] **Step 2: Run matcher tests and verify the source boundary passes**

Run:

```bash
pytest Tests/test_alert_matcher.py -q
```

Expected result: every matcher test passes, including both new `mygewo` tests and the existing private-handover tests.

- [ ] **Step 3: Write the user-delivery regression before changing the kind list**

Add this test to `TestDeliverUserAlerts` in `Project/Tests/test_run_coop.py`:

```python
    @patch("Integration.telegram_bot.TelegramBot")
    def test_mygewo_alert_is_delivered(self, TB):
        TB.return_value.send_message.return_value = True
        os.environ["TELEGRAM_MAIN_BOT_TOKEN"] = "tok"
        alert = {"_id": "mygewo", "kind": "mygewo", "keywords": [],
                 "telegram_chat_id": "-100", "confirmed": True}
        handler = self._handler([])
        handler.get_active_alerts.side_effect = (
            lambda kinds: [alert] if "mygewo" in kinds else [])
        listing = _l(
            url="https://mygewo.at/genossenschaftswohnungen/angebot/new",
            coop_source="bautraeger_direct")

        self.assertEqual(run_coop.deliver_user_alerts(handler, [listing]), 1)
        handler.get_active_alerts.assert_called_once_with(
            ["listings", "coop_private", "keyword", "mygewo", None])
        TB.assert_called_once_with("tok", "-100")
```

Update the existing legacy missing-kind assertion in the same class to expect the added `mygewo` kind:

```python
        handler.get_active_alerts.assert_called_once_with(
            ["listings", "coop_private", "keyword", "mygewo", None])
```

- [ ] **Step 4: Run the delivery regression and verify it fails for the missing query kind**

Run from `Project/`:

```bash
pytest Tests/test_run_coop.py::TestDeliverUserAlerts::test_mygewo_alert_is_delivered -q
```

Expected result: `FAIL` with `0 != 1`, because `USER_ALERT_KINDS` does not yet request `mygewo`.

- [ ] **Step 5: Add `mygewo` only to private user-alert kinds**

Change the constants in `Project/run_coop.py` to:

```python
USER_ALERT_KINDS = ["listings", "coop_private", "keyword", "mygewo", None]
CHANNEL_ALERT_KINDS = ["coop_private", "keyword"]
```

Keep `deliver_user_alerts()` and the channel query call sites unchanged.

- [ ] **Step 6: Run the focused Python regressions**

Run:

```bash
pytest Tests/test_alert_matcher.py Tests/test_run_coop.py::TestDeliverUserAlerts -q
```

Expected result: all selected tests pass, including the legacy missing-kind, MyGEWO delivery, Telegram, email, retry, and failure-path tests.

### Task 3: Lock down broadcast isolation

**Files:**
- Modify: `Project/Tests/test_coop_channel_ledger.py:265-285`
- Source invariant: `Project/run_coop.py:60`

- [ ] **Step 1: Add a channel-isolation regression**

Add this test to `TestChannelFilter`:

```python
    def test_mygewo_alert_does_not_govern_coop_channel(self):
        alert = {"_id": "mygewo", "kind": "mygewo", "telegram_chat_id": "-100"}
        ledger = FakeLedger()
        handler = _handler(ledger, alerts=[alert])
        handler.get_alert_subscriptions.side_effect = (
            lambda kinds: [alert] if "mygewo" in kinds else [])
        bots = _bot_factory()

        self.assertEqual(_poll(handler, [_l()], bots), 0)

        self.assertEqual(_sends(bots[0]), 0)
        handler.get_alert_subscriptions.assert_called_once_with(
            ["coop_private", "keyword"])
```

- [ ] **Step 2: Run the channel suite before changing channel code**

Run:

```bash
pytest Tests/test_coop_channel_ledger.py -q
```

Expected result: all channel tests pass. This test should pass without a channel-code change because `CHANNEL_ALERT_KINDS` is intentionally unchanged.

### Task 4: Extend API validation

**Files:**
- Create: `dashboard/app/api/saved-searches/alert/route.test.ts`
- Modify: `dashboard/app/api/saved-searches/alert/route.ts:14-21,109-112`

- [ ] **Step 1: Write the API tests first**

Create `dashboard/app/api/saved-searches/alert/route.test.ts` with mocked database and provider modules:

```typescript
import { beforeEach, describe, expect, it, jest } from '@jest/globals';
import type { NextRequest } from 'next/server';

const mockInsertOne = jest.fn();
const mockCollection = { insertOne: mockInsertOne };
const mockDb = { collection: jest.fn(() => mockCollection) };
const mockGetDb = jest.fn();
const mockGetOrCreateUserId = jest.fn();
const mockSetUserCookie = jest.fn();
const mockSendMail = jest.fn();
const mockConfirmationEmail = jest.fn(() => '<p>confirm</p>');

class MockObjectId {
  constructor(readonly value = '507f1f77bcf86cd799439011') {}

  toString() {
    return this.value;
  }
}

jest.mock('@/lib/mongodb', () => ({
  getDb: mockGetDb,
  ObjectId: MockObjectId,
}), { virtual: true });

jest.mock('@/lib/user', () => ({
  getOrCreateUserId: mockGetOrCreateUserId,
  setUserCookie: mockSetUserCookie,
}), { virtual: true });

jest.mock('@/lib/mailer', () => ({
  sendMail: mockSendMail,
  confirmationEmail: mockConfirmationEmail,
}), { virtual: true });

import { POST } from './route';

function request(body: Record<string, unknown>): NextRequest {
  return { json: async () => body } as unknown as NextRequest;
}

beforeEach(() => {
  jest.clearAllMocks();
  mockGetDb.mockReturnValue(mockDb);
  mockGetOrCreateUserId.mockReturnValue('user-1');
  mockSendMail.mockResolvedValue({ ok: false, error: 'SMTP unavailable' });
});

describe('POST /api/saved-searches/alert kinds', () => {
  it('accepts an all-MyGEWO alert kind', async () => {
    const response = await POST(request({
      kind: 'mygewo',
      telegram_chat_id: '-100123456',
    }));
    const body = await response.json() as { kind: string };

    expect(response.status).toBe(201);
    expect(body.kind).toBe('mygewo');
    expect(mockInsertOne).toHaveBeenCalledWith(
      expect.objectContaining({ kind: 'mygewo' }));
  });

  it('rejects an unknown alert kind before storing it', async () => {
    const response = await POST(request({
      kind: 'not-a-feed',
      telegram_chat_id: '-100123456',
    }));
    const body = await response.json() as { error: string };

    expect(response.status).toBe(400);
    expect(body.error).toBe('Invalid kind');
    expect(mockInsertOne).not.toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: Run the API tests and verify the acceptance test fails**

Run from `dashboard/`:

```bash
npx jest app/api/saved-searches/alert/route.test.ts --runInBand
```

Expected result: the `mygewo` test fails with HTTP `400`, while the unknown-kind test remains green.

- [ ] **Step 3: Add `mygewo` to the API contract and validation**

Update the `SubscribeBody.kind` documentation and type to include `mygewo`, then replace the inline allowlist with the four supported kinds:

```typescript
  /** Which feed to watch. 'listings' is the original behaviour. 'coop_private'
   * requires the private-transfer rubric. 'keyword' watches the mixed feed.
   * 'mygewo' watches builder-direct co-op rentals only. */
  kind?: 'listings' | 'coop_private' | 'keyword' | 'mygewo';
```

Keep the existing validation shape, changing only its allowlist:

```typescript
  if (!['listings', 'coop_private', 'keyword', 'mygewo'].includes(kind)) {
    return NextResponse.json({ error: 'Invalid kind' }, { status: 400 });
  }
```

- [ ] **Step 4: Run the API tests green**

Run:

```bash
npx jest app/api/saved-searches/alert/route.test.ts --runInBand
```

Expected result: 2 tests pass.

### Task 5: Update the dashboard form and browser regression

**Files:**
- Modify: `dashboard/app/alerts/page.tsx:34-46,94-101,135-167,226-270`
- Modify: `dashboard/tests/alerts-page.spec.ts:81-121`

- [ ] **Step 1: Write the browser regression before changing the form**

Add this test after the existing form-render test. The current form should fail at the unchecked/default assertions:

```typescript
test('defaults to all builder-direct MyGEWO rentals', async ({ page }) => {
  let posted: Record<string, unknown> | null = null;
  await page.route(ALERT_API, async (route) => {
    if (route.request().method() === 'POST') {
      posted = route.request().postDataJSON() as Record<string, unknown>;
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
  await expect(page.getByTestId('alert-keywords')).toHaveValue('');
  await page.getByTestId('alert-chatid').fill('-100123456');
  await page.getByTestId('alert-submit').click();

  await expect(page.getByTestId('alert-status')).toBeVisible();
  expect(posted).not.toBeNull();
  expect(posted?.kind).toBe('mygewo');
  expect(posted?.keywords).toEqual([]);
});
```

Update the existing keyword payload test to call
`await page.getByTestId('alert-private-only').check();` before submitting, so it continues to verify the explicit private-handover path and still expects `coop_private`.

- [ ] **Step 2: Run the targeted browser spec and verify the new test fails**

Start the dashboard dev server on the Playwright port from `dashboard/`:

```bash
PORT=3010 npm run dev
```

With the server running, run:

```bash
npx playwright test tests/alerts-page.spec.ts --reporter=dot
```

Expected result: the new test fails because the current checkbox is checked and the keyword field contains the old marker list.

- [ ] **Step 3: Make the all-MyGEWO form the default**

Remove the prefilled default keyword string and initialize the form as follows:

```tsx
const [keyword, setKeyword] = useState('');
const [privateOnly, setPrivateOnly] = useState(false);
```

Submit the explicit kind while preserving custom keyword narrowing:

```tsx
kind: privateOnly ? 'coop_private' : 'mygewo',
keywords: parseKeywords(keyword),
```

Reset `keyword` to `''` after creation. Update the copy so it says the unchecked mode watches all builder-direct MyGEWO rentals, the checked mode requires a private tenant handover, and blank keywords match every unit in the selected feed. Keep the existing test id, numeric filters, channel fields, status handling, and delete/test actions.

- [ ] **Step 4: Run the targeted browser spec green**

Run while the same server is running:

```bash
npx playwright test tests/alerts-page.spec.ts --reporter=dot
```

Expected result: every test in `alerts-page.spec.ts` passes, including the all-MyGEWO default and explicit private-handover test.

### Task 6: Full verification and handoff

**Files:**
- Test: `Project/Tests/test_alert_matcher.py`
- Test: `Project/Tests/test_run_coop.py`
- Test: `Project/Tests/test_coop_channel_ledger.py`
- Test: `dashboard/app/api/saved-searches/alert/route.test.ts`
- Test: `dashboard/tests/alerts-page.spec.ts`

- [ ] **Step 1: Run the complete Python suite**

From `Project/`:

```bash
pytest Tests -v --tb=short
```

Expected result: zero failures, including the legacy compatibility and all-MyGEWO alert regressions.

- [ ] **Step 2: Run the complete dashboard Jest suite**

From `dashboard/`:

```bash
npm test -- --runInBand
```

Expected result: zero failures, including the API kind tests.

- [ ] **Step 3: Run the dashboard production build**

From `dashboard/`:

```bash
npm run build
```

Expected result: Next.js compiles and type-checks successfully.

- [ ] **Step 4: Run the full Playwright suite**

With the dashboard server available on port 3010:

```bash
npx playwright test --reporter=line
```

Expected result: zero test failures and no console errors on the required dashboard routes. Stop the dev server afterward:

```bash
pkill -f "next dev"
```

- [ ] **Step 5: Refresh and inspect the code graph**

From the repository root:

```bash
graphify update .
```

Keep generated `graphify-out/` churn separate from the source diff.

- [ ] **Step 6: Inspect the final source diff**

Run:

```bash
```

Confirm the only behavior changes are the explicit all-MyGEWO user feed, its API/UI coverage, and preservation of private/broadcast isolation. Leave changes uncommitted and do not push or deploy until explicitly authorized.
