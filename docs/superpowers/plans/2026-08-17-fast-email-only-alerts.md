# Fast Email-Only Alerts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver newly matched Genossenschaft listings to a confirmed email without requiring Telegram, including dashboard verification and crash-safe retries.

**Architecture:** cron-job.org sends a minutely `repository_dispatch` POST to GitHub. Each dispatched workflow performs one source poll. New mygewo and Willhaben candidates are matched before upsert, claimed in the existing `(alert_id, url_hash)` ledger, and sent through independently tracked Telegram/email channels. GitHub Actions remains the latency floor at roughly 2-3 minutes.

**Tech Stack:** Python 3.11, pytest/unittest, MongoDB through `MongoDBHandler`, Next.js 15 App Router, TypeScript/Jest, Playwright, GitHub Actions.

---

## Preflight: Repair cron-job.org authentication

The repository URL is valid. GitHub returns `404` for this endpoint when the
request has no usable authorization or the token cannot access the repository.

In cron-job.org, edit the existing job:

- Method: `POST`
- URL: `https://api.github.com/repos/vladbrincoveanu/ImmoAgent/dispatches`
- Header: `Accept: application/vnd.github+json`
- Header: `Authorization: Bearer <fine-grained PAT>`
- Header: `Content-Type: application/json`
- Header: `X-GitHub-Api-Version: 2022-11-28`
- Raw body: `{"event_type":"coop-poll"}`
- Schedule: `* * * * *`, timezone `Europe/Vienna`

The fine-grained PAT must grant repository access to only
`vladbrincoveanu/ImmoAgent` and `Contents: Read and write`. The PAT must be in a
custom HTTP header, never in the URL or request body. A test run must return
`204 No Content`. Do not place the PAT in this repository or send it in chat.

This is an external manual action, not a code change. The local implementation
can be tested independently while the job is being corrected.

---

## File Map

| File | Responsibility | Change |
|---|---|---|
| `dashboard/lib/mailer.ts` | Dashboard SMTP transport and HTML templates | Add escaped alert-test email template |
| `dashboard/lib/mailer.test.ts` | Pure mailer template tests | Create |
| `dashboard/lib/alert-test.ts` | Pure email/Telegram test-channel policy | Create |
| `dashboard/lib/alert-test.test.ts` | Channel-policy regression tests | Create |
| `dashboard/app/api/saved-searches/alert/test/route.ts` | Alert destination verification API | Support confirmed email and mixed channels |
| `dashboard/app/alerts/page.tsx` | Alert form/list/test UI | Remove Telegram-only copy; rename test action |
| `dashboard/tests/alerts-page.spec.ts` | Real DOM alert flow | Add email-only test behavior |
| `Project/Application/alert_email.py` | Python alert email rendering/SMTP | Expose reusable subject/body and prepared retry send |
| `Project/Application/alert_dispatcher.py` | Per-pair delivery and recovery | Persist/send/retry channels independently |
| `Project/Integration/mongodb_handler.py` | Mongo delivery ledger boundary | Store email payload and channel sent flags |
| `Project/Tests/test_alert_dispatcher.py` | Dispatcher regression tests | Add email-only and partial-channel cases |
| `Project/Tests/test_run_coop.py` | Poll integration tests | Cover new mygewo alert candidates and pre-upsert delivery |
| `Project/run_coop.py` | Feed polling orchestration | Combine new candidates and deliver before upsert |
| `.github/workflows/coop-fast-poll.yml` | CI poll trigger | Document minutely external trigger; use 60s fallback interval |
| `docs/ALERTS_SETUP.md` | Operator setup/runbook | Document cron-job.org, email-only setup, and real SLA |
| `docs/superpowers/specs/2026-08-17-fast-email-only-alerts-design.md` | Approved design | Already written |

---

### Task 1: Dashboard Email-Only Verification

**Files:**
- Modify: `dashboard/lib/mailer.ts`
- Create: `dashboard/lib/mailer.test.ts`
- Create: `dashboard/lib/alert-test.ts`
- Modify: `dashboard/app/api/saved-searches/alert/test/route.ts`
- Modify: `dashboard/app/alerts/page.tsx`
- Test: `dashboard/tests/alerts-page.spec.ts`

- [ ] **Step 1: Write the failing pure mailer test**

Add a Jest suite that imports `alertTestEmail` and proves dynamic keyword text
is HTML escaped:

```ts
import { describe, expect, it } from '@jest/globals';
import { alertTestEmail } from './mailer';

describe('alertTestEmail', () => {
  it('escapes alert keywords before putting them in HTML', () => {
    const html = alertTestEmail(['<script>alert(1)</script>']);
    expect(html).not.toContain('<script>');
    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;');
  });
});
```

- [ ] **Step 2: Run the focused dashboard test and verify it fails**

Run from `dashboard/`:

```bash
npm test -- --runInBand lib/mailer.test.ts
```

Expected failure: `alertTestEmail` is not exported.

- [ ] **Step 3: Add the escaped test-email renderer**

In `dashboard/lib/mailer.ts`, add a local HTML escape helper and export this
function without changing `sendMail`:

```ts
function escapeHtml(value: string): string {
  return value.replace(/[&<>"']/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[char] ?? char));
}

export function alertTestEmail(keywords: string[]): string {
  const label = keywords.length
    ? keywords.map(escapeHtml).join(', ')
    : '(alle Treffer)';
  return `
    <div style="font-family:sans-serif;max-width:520px;margin:0 auto;color:#16243a">
      <h2 style="font-size:20px;margin-bottom:8px">ImmoScouter Alert-Test</h2>
      <p style="color:#5b6b80;font-size:14px">
        Diese Test-E-Mail bestätigt, dass neue passende Genossenschaftswohnungen
        an diese Adresse gesendet werden.
      </p>
      <p style="font-size:13px;color:#5b6b80"><b>Suchbegriffe:</b> ${label}</p>
    </div>
  `;
}
```

- [ ] **Step 4: Run the focused dashboard test and verify it passes**

```bash
npm test -- --runInBand lib/mailer.test.ts
```

Expected: one passing suite.

- [ ] **Step 5: Write the failing channel-policy tests**

Create `dashboard/lib/alert-test.test.ts` with a pure policy test. This keeps
the channel matrix independent of Next.js, MongoDB, and provider mocks:

```ts
import { describe, expect, it } from '@jest/globals';
import { testChannels } from './alert-test';

describe('testChannels', () => {
  it('allows a confirmed email without Telegram', () => {
    expect(testChannels({
      telegram_chat_id: null, email: 'u@example.at', confirmed: true,
    })).toEqual({ telegram: false, email: true });
  });

  it('rejects an unconfirmed email when Telegram is absent', () => {
    expect(testChannels({
      telegram_chat_id: null, email: 'u@example.at', confirmed: false,
    })).toEqual({
      telegram: false, email: false,
      error: 'Confirm your email before testing email delivery.',
    });
  });

  it('allows Telegram while email confirmation is pending', () => {
    expect(testChannels({
      telegram_chat_id: '-100123456', email: 'u@example.at', confirmed: false,
    })).toEqual({ telegram: true, email: false });
  });

  it('allows both channels after email confirmation', () => {
    expect(testChannels({
      telegram_chat_id: '-100123456', email: 'u@example.at', confirmed: true,
    })).toEqual({ telegram: true, email: true });
  });

  it('rejects an alert with no destination', () => {
    expect(testChannels({ telegram_chat_id: null, email: null, confirmed: false }))
      .toEqual({ telegram: false, email: false, error: 'No usable alert channel.' });
  });
});
```

- [ ] **Step 6: Run the focused channel-policy tests and verify they fail**

```bash
npm test -- --runInBand lib/alert-test.test.ts
```

Expected failure: `testChannels` is not exported.

- [ ] **Step 7: Implement the pure channel policy**

Create `dashboard/lib/alert-test.ts`:

```ts
export type AlertTestRecord = {
  telegram_chat_id?: string | null;
  email?: string | null;
  confirmed?: boolean;
};

export type AlertTestChannels = {
  telegram: boolean;
  email: boolean;
  error?: string;
};

export function testChannels(alert: AlertTestRecord): AlertTestChannels {
  const telegram = Boolean(alert.telegram_chat_id);
  const hasEmail = Boolean(alert.email);
  const email = hasEmail && Boolean(alert.confirmed);
  if (telegram || email) return { telegram, email };
  return {
    telegram: false,
    email: false,
    error: hasEmail
      ? 'Confirm your email before testing email delivery.'
      : 'No usable alert channel.',
  };
}
```

- [ ] **Step 8: Run the channel-policy tests and verify they pass**

```bash
npm test -- --runInBand lib/alert-test.test.ts lib/mailer.test.ts
```

Expected: all channel and mailer tests pass.

- [ ] **Step 9: Implement the route channel matrix**

In `dashboard/app/api/saved-searches/alert/test/route.ts`:

- Keep the user-scoped Mongo lookup and ObjectId validation.
- Read `telegram_chat_id` and `email` from the stored alert.
- If there is no Telegram ID and no email, return `400` with a usable-channel error.
- If there is an email but `confirmed` is false and no Telegram ID exists, return
  `400` telling the user to confirm the email.
- Call `testChannels(alert)` and return its `error` before contacting providers.
- Send the existing Telegram probe when a chat ID exists.
- Send `sendMail({ to: email, subject: 'ImmoScouter Alert-Test', html: alertTestEmail(keys) })`
  when email exists and is confirmed.
- If Telegram fails, return the provider detail as today and do not hide it behind
  an email success.
- If email fails, return its SMTP error with status `502`.
- If both send successfully, return `{ ok: true, channels: ['telegram', 'email'] }`.
- Return `{ ok: true, channels: [...] }` for a single successful channel.

- [ ] **Step 10: Update the dashboard copy and test**

In `dashboard/app/alerts/page.tsx`:

- Change the latency sentence to say `Telegram or email notification`.
- Change the row action label from `Test` to `Test notification`.
- Keep `data-testid="alert-test"` unchanged.
- Explain that email can be used alone and must be confirmed.
- Use `json.message` or channel-aware success text in `sendTest`.

Add a Playwright case to `dashboard/tests/alerts-page.spec.ts` with an email-only
stored row and a mocked successful `/api/saved-searches/alert/test` response. It
must click the real button and assert the visible status contains `email`.

- [ ] **Step 11: Run the targeted DOM verification**

```bash
npx playwright test tests/alerts-page.spec.ts --grep "email-only|latency|stored alert"
```

Expected: all selected tests pass and the assertions target rendered DOM nodes.

- [ ] **Step 12: Commit dashboard verification changes**

```bash
git add dashboard/lib/mailer.ts dashboard/lib/mailer.test.ts \
  dashboard/lib/alert-test.ts dashboard/lib/alert-test.test.ts \
  dashboard/app/api/saved-searches/alert/test/route.ts \
  dashboard/app/alerts/page.tsx dashboard/tests/alerts-page.spec.ts
git commit -m "feat: support email-only alert tests"
```

---

### Task 2: Durable Per-Channel Python Delivery

**Files:**
- Modify: `Project/Application/alert_email.py`
- Modify: `Project/Application/alert_dispatcher.py`
- Modify: `Project/Integration/mongodb_handler.py`
- Test: `Project/Tests/test_alert_dispatcher.py`

- [ ] **Step 1: Add failing dispatcher tests**

Extend the in-memory handler so `claim_delivery` accepts email payload fields,
tracks `telegram_sent` and `email_sent`, and exposes
`mark_delivery_channel_sent`. Add these tests:

```python
def test_email_only_dispatch_sends_and_marks_email_sent():
    handler, sent = _Handler(), []
    alert = {**_ALERT, "telegram_chat_id": None, "email": "u@example.at"}
    ok = dispatch(
        alert, _L(), False, handler, token=None,
        send_email=lambda address, listing: sent.append(address) or True,
    )
    assert ok is True
    assert sent == ["u@example.at"]
    assert _statuses(handler) == ["sent"]


def test_email_failure_leaves_only_email_pending():
    handler = _Handler()
    alert = {**_ALERT, "telegram_chat_id": None, "email": "u@example.at"}
    assert dispatch(
        alert, _L(), False, handler, token=None,
        send_email=lambda address, listing: False,
    ) is False
    row = next(iter(handler.rows.values()))
    assert row["status"] == "pending"
    assert row["email_sent"] is False


def test_pending_email_is_retried():
    handler = _Handler()
    alert = {**_ALERT, "telegram_chat_id": None, "email": "u@example.at"}
    dispatch(alert, _L(), False, handler, token=None,
             send_email=lambda address, listing: False)
    sent = []
    assert retry_pending(
        handler, token=None,
        send_email=lambda address, subject, body: sent.append(address) or True,
    ) == 1
    assert sent == ["u@example.at"]


def test_telegram_success_does_not_hide_email_failure():
    handler, telegram, email = _Handler(), [], []
    alert = {**_ALERT, "email": "u@example.at"}
    assert dispatch(
        alert, _L(), False, handler, token="t",
        send_telegram=lambda chat, message: telegram.append(chat) or True,
        send_email=lambda address, listing: email.append(address) or False,
    ) is True
    row = next(iter(handler.rows.values()))
    assert row["status"] == "pending"
    assert row["telegram_sent"] is True
    assert row["email_sent"] is False
```

- [ ] **Step 2: Run the focused Python tests and verify they fail**

```bash
cd Project/Tests && python -m pytest test_alert_dispatcher.py -q
```

Expected failure: the handler and dispatcher do not accept/store email delivery
state or retry email payloads.

- [ ] **Step 3: Add prepared email rendering and sending**

In `Project/Application/alert_email.py`, expose a stable subject/body pair and a
prepared-content sender while keeping `send_alert_email(to_addr, listing)` for
initial delivery:

```python
ALERT_EMAIL_SUBJECT = "Neue passende Wohnungsanzeige"


def build_alert_email(listing):
    return ALERT_EMAIL_SUBJECT, _body(listing)


def send_alert_email_content(to_addr: str, subject: str, body: str) -> bool:
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    if not user or not password:
        logger.error("SMTP_USER/SMTP_PASSWORD unset — alert email NOT sent to "
                     f"{to_addr}")
        return False

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to_addr
    msg.set_content(body)
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.starttls()
            server.login(user, password)
            server.send_message(msg)
        return True
    except Exception as e:
        logger.error(f"alert email to {to_addr} failed: {e}")
        return False


def send_alert_email(to_addr: str, listing) -> bool:
    subject, body = build_alert_email(listing)
    return send_alert_email_content(to_addr, subject, body)
```

Do not duplicate SMTP setup in the dispatcher.

- [ ] **Step 4: Extend Mongo ledger methods**

In `MongoDBHandler.claim_delivery`, store `email`, `email_subject`,
`email_body`, `telegram_sent`, and `email_sent`. Set an unconfigured channel's
flag to `True` at claim time. Preserve the existing unique index and pending row
behavior.

Add:

```python
def mark_delivery_channel_sent(self, alert_id, url_hash: str, channel: str) -> None:
    field = {"telegram": "telegram_sent", "email": "email_sent"}.get(channel)
    if not field:
        raise ValueError(f"unknown delivery channel: {channel}")
    row = self.db["alert_deliveries"].find_one_and_update(
        {"alert_id": alert_id, "url_hash": url_hash},
        {"$set": {field: True}},
        return_document=pymongo.ReturnDocument.AFTER,
    )
    if row and (
        (not row.get("chat_id") or row.get("telegram_sent"))
        and (not row.get("email") or row.get("email_sent"))
    ):
        self.db["alert_deliveries"].update_one(
            {"alert_id": alert_id, "url_hash": url_hash},
            {"$set": {"status": "sent", "sent_at": datetime.now(timezone.utc)}},
        )
```

Keep `mark_delivery_sent` for existing callers and old rows. Its existing final
status behavior remains unchanged.

- [ ] **Step 5: Update dispatcher initial send and retry paths**

In `alert_dispatcher.py`:

- Import `build_alert_email` and `send_alert_email_content` lazily in default
  sender helpers.
- Build and pass email subject/body into `claim_delivery` before sending.
- Call `mark_delivery_channel_sent(..., "telegram")` only after a successful
  Telegram send.
- Call `mark_delivery_channel_sent(..., "email")` only after a successful email
  send.
- Return true when at least one channel succeeds, preserving delivery counts.
- Leave the row pending when any configured channel fails.
- Make `retry_pending` send stored Telegram message and stored email subject/body
  independently, then mark only the successful channel.
- Treat old rows without email fields as Telegram-only rows.
- Never derive an email address or message from a fresh lookup during retry.

The retry callback signature for prepared email is
`(address, subject, body) -> bool`; the initial injected callback remains
`(address, listing) -> bool` so current tests and call sites stay simple.

- [ ] **Step 6: Run focused Python tests and full alert tests**

```bash
cd Project/Tests && python -m pytest test_alert_dispatcher.py test_alert_matcher.py -q
```

Expected: all focused dispatcher and matcher tests pass.

- [ ] **Step 7: Commit the delivery milestone**

```bash
git add Project/Application/alert_email.py Project/Application/alert_dispatcher.py \
  Project/Integration/mongodb_handler.py Project/Tests/test_alert_dispatcher.py
git commit -m "feat: make alert delivery email-capable"
```

---

### Task 3: Match New Genossenschaft Listings Before Upsert

**Files:**
- Modify: `Project/run_coop.py`
- Test: `Project/Tests/test_run_coop.py`

- [ ] **Step 1: Write failing candidate-selection tests**

Add `new_alert_candidates(handler, seen, new_from_willhaben)` to the test
surface and cover the two newness cases:

```python
def test_new_mygewo_listing_is_a_user_alert_candidate():
    handler = MagicMock()
    handler.get_listing.return_value = None
    listing = _l(url="https://mygewo.at/angebot/new")

    assert run_coop.new_alert_candidates(handler, [listing], []) == [listing]
    handler.get_listing.assert_called_once_with(listing.url)


def test_existing_mygewo_listing_is_not_a_new_user_alert_candidate():
    handler = MagicMock()
    handler.get_listing.return_value = {"_id": "existing"}
    listing = _l(url="https://mygewo.at/angebot/existing")

    assert run_coop.new_alert_candidates(handler, [listing], []) == []
```

Add one orchestration test with an ordered event list:

```python
@patch("run_coop.load_coop_alerts", return_value={})
@patch("run_coop.validate_url", return_value=True)
@patch("run_coop.poll_source")
@patch("run_coop.MongoDBHandler")
def test_user_alerts_run_before_mygewo_upsert(mongo, poll, validate, alerts):
    handler = _mongo_mock(get_listing_ret=None)
    events = []
    listing = _l(url="https://mygewo.at/angebot/new")
    listing.builder_url = ""
    listing.image_url = ""
    handler.upsert_coop_listing.side_effect = lambda doc: events.append("upsert")
    mongo.return_value = handler
    poll.return_value = [listing]

    with patch.object(
        run_coop, "deliver_user_alerts",
        side_effect=lambda h, candidates: events.append(("deliver", candidates)),
    ), patch.dict(run_coop.coop.SOURCES,
                  {"MYGEWO": {"url": "u", "fetcher": "fetch_all_mygewo"}},
                  clear=True), patch.dict(os.environ,
                  {"WILLHABEN_PRIVATE_COOP": "0"}):
        assert run_coop.run(no_send=False) == 0

    assert events[0] == ("deliver", [listing])
    assert events[1] == "upsert"
```

- [ ] **Step 2: Run the focused poll tests and verify the new tests fail**

```bash
cd Project/Tests && python -m pytest test_run_coop.py -q
```

Expected failure: `new_alert_candidates` is not defined, and the current
orchestration sends user alerts only from `new_from_willhaben` after upsert.

- [ ] **Step 3: Collect candidates from both sources**

After all adapters and the Willhaben crawl have populated `seen`:

```python
new_mygewo = [
    listing for listing in seen
    if "mygewo.at" in (listing.url or "")
    and handler.get_listing(listing.url) is None
]
user_alert_candidates = new_mygewo + new_from_willhaben
```

Do not use `sent_to_telegram` as the newness test. Existing listings may have
never been sent to the owner's channel but must not be treated as newly posted.

- [ ] **Step 4: Move user alert delivery before the detail/upsert loop**

Replace the current late call:

```python
if not no_send:
    deliver_user_alerts(handler, new_from_willhaben)
```

with a call immediately after candidate collection and before detail fetches and
upserts:

```python
if not no_send:
    deliver_user_alerts(handler, user_alert_candidates)
```

Keep the owner channel alert loop and all upserts unchanged otherwise. This
ordering ensures a canceled workflow cannot upsert a listing and then lose the
only in-memory reference needed for a user alert.

- [ ] **Step 5: Run the focused poll tests and full Python alert tests**

```bash
cd Project/Tests && python -m pytest test_run_coop.py test_alert_dispatcher.py test_alert_matcher.py -q
```

Expected: all pass, including the new mygewo candidate-ordering tests.

- [ ] **Step 6: Commit the poll milestone**

```bash
git add Project/run_coop.py Project/Tests/test_run_coop.py
git commit -m "fix: alert on new genossenschaft listings"
```

---

### Task 4: Align Workflow and Operator Documentation

**Files:**
- Modify: `.github/workflows/coop-fast-poll.yml`
- Modify: `docs/ALERTS_SETUP.md`

- [ ] **Step 1: Update workflow comments and fallback interval**

In `.github/workflows/coop-fast-poll.yml`:

- Change dispatch comments from approximately two minutes to one minute.
- Set `POLL_INTERVAL_SECONDS: 60` for the fallback window.
- Keep repository dispatch as a one-poll path through
  `coop-poll-window.sh`.
- Keep `POLL_WINDOW_MINUTES` empty for dispatch events so the script sets it to
  zero.
- Change the step label from Telegram-only wording to a neutral fast alert label.
- Keep SMTP secrets exposed to the poll job.

- [ ] **Step 2: Update the setup guide**

In `docs/ALERTS_SETUP.md`:

- Document cron-job.org every minute in `Europe/Vienna`.
- Include the exact URL, `POST` method, four headers, and JSON body.
- State that a healthy dispatch returns `204 No Content`.
- Make Telegram optional and document email confirmation as the email consent
  step.
- Replace the old Pro-only and Telegram-required instructions with the current
  alert API behavior.
- Explain that the honest GitHub-based latency is about 2-3 minutes.
- Remove the known gap saying email is not retried; document per-channel retry
  behavior instead.
- Add checks for cron history, GitHub run history, poll logs, and alert delivery
  logs.

- [ ] **Step 3: Run shell syntax and workflow-local tests**

```bash
bash -n .github/scripts/coop-poll-window.sh
cd Project/Tests && python -m pytest test_coop_poll_window.py -q
```

Expected: shell syntax is clean and all poll-window tests pass.

- [ ] **Step 4: Commit workflow/docs milestone**

```bash
git add .github/workflows/coop-fast-poll.yml docs/ALERTS_SETUP.md
git commit -m "docs: configure minutely alert polling"
```

---

### Task 5: End-to-End Verification and Graph Refresh

**Files:**
- No new source files.
- Generated graph artifacts may change under `graphify-out/`; stage only graph
  files intentionally tracked by the task after reviewing the diff.

- [ ] **Step 1: Run Python regression suite**

```bash
cd Project/Tests && python -m pytest . -q
```

Expected: zero failures. If unrelated pre-existing failures occur, record their
test names and do not mask them.

- [ ] **Step 2: Run dashboard unit and type checks**

```bash
cd dashboard && npm test -- --runInBand
cd dashboard && npx tsc --noEmit
```

Expected: all Jest suites pass and TypeScript exits zero.

- [ ] **Step 3: Run targeted Playwright DOM tests**

```bash
cd dashboard && npx playwright test tests/alerts-page.spec.ts
```

Assert the actual rendered `data-testid="alerts-page"`, alert row, test button,
and status element. Do not replace these assertions with screenshots.

- [ ] **Step 4: Run the full Playwright suite**

```bash
cd dashboard && npx playwright test
```

Expected: full suite passes. Record any environment-only failures separately.

- [ ] **Step 5: Refresh the knowledge graph**

```bash
graphify update .
```

Verify that `alert_dispatcher.py`, `alert_email.py`, `run_coop.py`, and the
dashboard alert route remain present in the graph. Do not commit unrelated cache
churn without inspecting `git diff --stat`.

- [ ] **Step 6: Verify local branch state and intended commits**

```bash
git status --short --branch
```

Stage only task files. Never stage `.env`, PATs, SMTP passwords, bot tokens, or
unrelated pre-existing worktree changes.

- [ ] **Step 7: Confirm external trigger manually**

In cron-job.org, run the corrected job once. Expected:

- cron-job.org response: `204 No Content`.
- GitHub Actions: a new `coop-fast-poll` run.
- Workflow log: a source poll and `user alerts: N delivery(ies)` when a match exists.

Do not call the GitHub dispatch endpoint from local shell with a credential. The
cron job is the authorized external trigger.
