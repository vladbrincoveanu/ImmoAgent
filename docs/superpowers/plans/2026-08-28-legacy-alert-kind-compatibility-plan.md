# Legacy Alert Kind Compatibility Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver alerts created before the `kind` field existed while keeping legacy alerts out of broadcast co-op channel filtering.

**Architecture:** The user-alert poll passes `None` alongside explicit alert kinds. The existing MongoDB `$in` query interprets `None` as matching both explicit null and missing `kind` fields. The channel poll continues to pass only `coop_private` and `keyword`, so the two delivery paths remain isolated.

**Tech Stack:** Python, MongoDB/PyMongo, `unittest.mock`, pytest.

---

## File Map

- Modify `Project/Tests/test_run_coop.py` to model the old dashboard's confirmed email-only record with no `kind` or keyword.
- Modify `Project/run_coop.py` to request the legacy missing-kind records for private user delivery.
- Modify `Project/Integration/mongodb_handler.py` to document the `None` query sentinel and its missing/null-field semantics.

### Task 1: Write the failing legacy regression

**Files:**
- Modify: `Project/Tests/test_run_coop.py:658-674`

- [ ] **Step 1: Replace the current explicit-kind Telegram fixture**

Use the actual old dashboard shape and make the test fail against the current
`USER_ALERT_KINDS` list:

```python
    @patch("Application.alert_email.send_alert_email", return_value=True)
    def test_legacy_listings_alert_without_kind_is_delivered(self, mail):
        """Pre-kind dashboard alerts remain private user subscriptions."""
        alert = {
            "_id": "legacy",
            "email": "legacy@example.at",
            "params": {"district": "1100", "frequency": "daily"},
            "frequency": "daily",
            "confirmed": True,
        }
        handler = self._handler([])
        handler.get_active_alerts.side_effect = (
            lambda kinds: [alert] if None in kinds else [])
        listing = _l(url="https://willhaben.at/x")

        self.assertEqual(run_coop.deliver_user_alerts(handler, [listing]), 1)
        handler.get_active_alerts.assert_called_once_with(
            ["listings", "coop_private", "keyword", None])
        mail.assert_called_once()
```

- [ ] **Step 2: Run the focused test and verify the expected failure**

Run from `Project/`:

```bash
pytest Tests/test_run_coop.py::TestDeliverUserAlerts::test_legacy_listings_alert_without_kind_is_delivered -q
```

Expected result: `FAIL` with an assertion showing `0 != 1`, because the current
poller does not request `None` in its user-alert kinds.

### Task 2: Implement the minimal compatibility query

**Files:**
- Modify: `Project/run_coop.py:53-60`
- Modify: `Project/Integration/mongodb_handler.py:685-700`

- [ ] **Step 1: Include the legacy sentinel only for private user alerts**

Change the constant to:

```python
USER_ALERT_KINDS = ["listings", "coop_private", "keyword", None]
CHANNEL_ALERT_KINDS = ["coop_private", "keyword"]
```

Keep `deliver_user_alerts()` calling `get_active_alerts(USER_ALERT_KINDS)` and
keep `run()` calling `get_alert_subscriptions(CHANNEL_ALERT_KINDS)`.

- [ ] **Step 2: Document the sentinel in the MongoDB handler**

Update `get_active_alerts()`'s docstring to state that its kind argument may be a
string or list of values, and that a list containing `None` intentionally
matches pre-kind subscriptions whose `kind` is missing or null through the
existing `$in` query.

Do not change the query shape, add a migration, or alter
`get_alert_subscriptions()`.

- [ ] **Step 3: Run the focused regression and verify green**

Run:

```bash
pytest Tests/test_run_coop.py::TestDeliverUserAlerts::test_legacy_listings_alert_without_kind_is_delivered -q
```

Expected result: `PASS`.

### Task 3: Verify user/channel separation and full suites

**Files:**
- Test: `Project/Tests/test_run_coop.py`
- Test: `Project/Tests/test_coop_channel_ledger.py`
- Test: `Project/Tests/test_alert_dispatcher.py`
- Build: `dashboard/`

- [ ] **Step 1: Run the complete Python suite**

Run from `Project/`:

```bash
pytest Tests -v --tb=short
```

Expected result: all Python tests pass, with the suite retaining its current
count of 274 tests.

- [ ] **Step 2: Run the complete dashboard suite**

Run from `dashboard/`:

```bash
npm test -- --runInBand
```

Expected result: 8 suites and 79 tests pass.

- [ ] **Step 3: Build the dashboard**

Run from `dashboard/`:

```bash
npm run build
```

Expected result: Next.js compiles, type-checks, and generates all pages without
errors.

- [ ] **Step 4: Refresh the code graph**

Run from the repository root:

```bash
graphify update .
```

Review the resulting graph changes separately from the source diff; do not add
generated graph churn to the alert fix commit unless repository policy requires
it.

### Task 4: Review and commit

**Files:**
- Commit: `Project/run_coop.py`
- Commit: `Project/Integration/mongodb_handler.py`
- Commit: `Project/Tests/test_run_coop.py`

- [ ] **Step 1: Inspect the focused diff**

Run:

```bash
git diff -- Project/run_coop.py Project/Integration/mongodb_handler.py Project/Tests/test_run_coop.py
```

Confirm the only behavior change is inclusion of missing/null-kind records in
private user delivery; broadcast channel kinds remain unchanged.

- [ ] **Step 2: Commit only the source and regression files**

Run:

```bash
git add Project/run_coop.py Project/Integration/mongodb_handler.py Project/Tests/test_run_coop.py
git commit -m "fix(alerts): preserve pre-kind subscriptions"
```

Do not push or open a pull request until explicitly authorized.
