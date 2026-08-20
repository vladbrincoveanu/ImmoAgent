# Co-op Telegram New-Only Size Filter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans (recommended) to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make source co-op Telegram feeds send only newly discovered qualifying URLs, with `area_m2 >= 75`, `rooms >= 3`, pre-send atomic claims, and permanent no-duplicate state.

**Architecture:** Keep scraping, MongoDB storage, user-created alerts, and Vienna buyer delivery separate. Select new source candidates from a pre-upsert URL lookup, pass both daily and fast-poll source routes through one shared co-op policy/delivery helper, and add non-expiring route claims to the existing MongoDB delivery ledger. Any uncertain Telegram attempt becomes terminal `uncertain`.

**Tech Stack:** Python 3.11, PyMongo, existing `TelegramBot`, pytest/unittest, `graphify update`.

---

## File Map

| File | Action | Responsibility |
| --- | --- | --- |
| `tests/test_telegram_vienna_delivery.py` | Modify | Add shared co-op policy, claim ordering, terminal uncertainty, and route-state tests first. |
| `Project/Application/telegram_delivery.py` | Modify | Add strict co-op policy and one-listing atomic source delivery helper. |
| `Project/Integration/mongodb_handler.py` | Modify | Add `coop` and `private_coop` route support with non-expiring claims. |
| `Project/Tests/test_run_coop.py` | Modify | Prove fast-poll source candidates use new-only and strict policy while user-alert behavior stays independent. |
| `Project/run_coop.py` | Modify | Send only pre-upsert new source candidates through shared delivery helper. |
| `tests/test_telegram_vienna_delivery.py` | Modify | Exercise daily main co-op route with mocked dependencies. |
| `Project/Application/main.py` | Modify | Batch-check co-op URLs before save and use shared source delivery. |
| `docs/superpowers/specs/2026-08-19-coop-telegram-new-only-filter-design.md` | Existing | Approved design; implementation must match it. |

## Task 1: Add Failing Shared Co-op Policy and Delivery Tests

**Files:**
- Modify: `tests/test_telegram_vienna_delivery.py`

- [ ] **Step 1: Add strict co-op policy tests.**

Import the new public API and add tests beside the existing Vienna filter tests:

```python
from Application.telegram_delivery import (
    COOP_MIN_AREA_M2,
    COOP_MIN_ROOMS,
    coop_filter_reason,
    send_coop_listing,
)


def coop_listing(**overrides):
    value = {
        "url": "https://example.test/coop-1",
        "title": "Neue Genossenschaft",
        "area_m2": 75.0,
        "rooms": 3.0,
    }
    value.update(overrides)
    return value


def test_coop_policy_uses_inclusive_area_and_room_boundaries():
    assert COOP_MIN_AREA_M2 == 75.0
    assert COOP_MIN_ROOMS == 3.0
    assert coop_filter_reason(coop_listing(area_m2=75.0, rooms=3.0)) is None
    assert coop_filter_reason(coop_listing(area_m2=74.99)) is not None
    assert coop_filter_reason(coop_listing(rooms=2.99)) is not None


@pytest.mark.parametrize("field", ["area_m2", "rooms"])
@pytest.mark.parametrize("value", [None, "75", True, math.nan, math.inf, -math.inf])
def test_coop_policy_rejects_missing_invalid_and_nonfinite_measurements(field, value):
    assert coop_filter_reason(coop_listing(**{field: value})) is not None
```

- [ ] **Step 2: Add pre-send ordering and terminal-state tests.**

Use mocks to prove no bot call occurs before a claim and that every attempted
Telegram call becomes terminal when confirmation is unavailable:

```python
def test_coop_delivery_claims_before_sending_and_marks_success():
    bot = Mock()
    bot.send_message.return_value = True
    mongo = Mock()
    events = []
    mongo.claim_listing_delivery.side_effect = lambda *args, **kwargs: events.append("claim") or True
    mongo.mark_listing_delivery_sent.side_effect = lambda *args, **kwargs: events.append("mark") or True

    assert send_coop_listing(
        coop_listing(), bot, mongo, "coop",
        url_validator=lambda url: events.append("url") or True,
        message_formatter=lambda listing: events.append("format") or "message",
    ) is True
    assert events == ["url", "claim", "format", "mark"]
    bot.send_message.assert_called_once_with("message")


def test_coop_delivery_skips_before_bot_when_claim_is_lost():
    bot = Mock()
    mongo = Mock()
    mongo.claim_listing_delivery.return_value = False

    assert send_coop_listing(coop_listing(), bot, mongo, "coop", url_validator=lambda _: True) is False
    bot.send_message.assert_not_called()


@pytest.mark.parametrize("send_result", [False, RuntimeError("telegram uncertain")])
def test_coop_delivery_quarantines_any_unconfirmed_attempt(send_result):
    bot = Mock()
    if isinstance(send_result, Exception):
        bot.send_message.side_effect = send_result
    else:
        bot.send_message.return_value = send_result
    mongo = Mock()
    mongo.claim_listing_delivery.return_value = True
    mongo.quarantine_listing_delivery.return_value = True

    assert send_coop_listing(coop_listing(), bot, mongo, "coop", url_validator=lambda _: True) is False
    mongo.release_listing_delivery.assert_not_called()
    mongo.quarantine_listing_delivery.assert_called_once()
    mongo.mark_listing_delivery_sent.assert_not_called()
```

- [ ] **Step 3: Run only the new tests and verify they fail for missing API.**

Run:

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter-telegram-new-only-filter
pytest -q tests/test_telegram_vienna_delivery.py -k 'coop_policy or coop_delivery'
```

Expected: collection or test failures because `COOP_MIN_AREA_M2`,
`coop_filter_reason`, and `send_coop_listing` do not exist yet.

- [ ] **Step 4: Commit the red test checkpoint.**

```bash
git add tests/test_telegram_vienna_delivery.py
git commit -m "test: define co-op Telegram delivery policy"
```

## Task 2: Implement Shared Co-op Policy and Delivery

**Files:**
- Modify: `Project/Application/telegram_delivery.py`
- Test: `tests/test_telegram_vienna_delivery.py`

- [ ] **Step 1: Add constants and strict policy.**

Reuse the existing numeric helpers and add:

```python
COOP_CHANNEL = "coop"
PRIVATE_COOP_CHANNEL = "private_coop"
COOP_MIN_AREA_M2 = 75.0
COOP_MIN_ROOMS = 3.0


def coop_filter_reason(listing: Any) -> Optional[str]:
    data = listing_dict(listing)
    url = data.get("url")
    if not isinstance(url, str) or not url.strip():
        return "missing or invalid URL"
    for field, minimum in (
        ("area_m2", COOP_MIN_AREA_M2),
        ("rooms", COOP_MIN_ROOMS),
    ):
        value = _policy_number(data.get(field))
        if value is None:
            return f"missing or invalid {field}"
        if value < minimum:
            return f"{field} {value:g} is below minimum {minimum:g}"
    return None
```

- [ ] **Step 2: Add one-listing source delivery with URL-only identity.**

The helper must validate, claim before calling Telegram, and quarantine any
attempt whose durable outcome is not confirmed. Pass an empty fingerprint so
source-feed identity is the approved URL-once rule:

```python
def send_coop_listing(
    listing,
    bot,
    mongo,
    channel: str,
    *,
    url_validator=validate_url,
    message_formatter=format_coop_message,
) -> bool:
    data = listing_dict(listing)
    reason = coop_filter_reason(data)
    if reason:
        logger.info("Skipping co-op source listing %r: %s", data.get("url"), reason)
        return False
    url = data["url"]
    try:
        valid = url_validator(url)
    except Exception as exc:
        logger.warning("Co-op URL validation failed for %s: %s", url, exc)
        valid = False
    if not valid:
        try:
            mongo.mark_url_invalid(url)
        except Exception as exc:
            logger.warning("Could not mark co-op URL invalid %s: %s", url, exc)
        return False

    claim_token = uuid.uuid4().hex
    try:
        claimed = mongo.claim_listing_delivery(
            url, "", channel, claim_token=claim_token, lease_seconds=None
        )
    except Exception as exc:
        logger.error("Could not claim co-op listing %s: %s", url, exc)
        return False
    if not claimed:
        logger.info("Skipping co-op listing already claimed or sent: %s", url)
        return False

    try:
        delivered = bool(bot.send_message(message_formatter(listing)))
    except Exception as exc:
        logger.error("Co-op Telegram send failed for %s: %s", url, exc)
        delivered = False
    if delivered:
        try:
            if mongo.mark_listing_delivery_sent(
                url, "", channel, claim_token=claim_token
            ):
                return True
        except Exception as exc:
            logger.error("Could not mark co-op listing sent %s: %s", url, exc)

    try:
        mongo.quarantine_listing_delivery(
            url, "", channel, claim_token=claim_token
        )
    except Exception as exc:
        logger.error("Could not quarantine co-op listing %s: %s", url, exc)
    return False
```

The implementation may use a small private helper if needed, but it must not
release a source claim after Telegram is attempted.

- [ ] **Step 3: Run the focused shared tests.**

```bash
pytest -q tests/test_telegram_vienna_delivery.py -k 'coop_policy or coop_delivery'
```

Expected: all new tests pass; existing Vienna tests remain green.

- [ ] **Step 4: Commit the shared helper.**

```bash
git add Project/Application/telegram_delivery.py tests/test_telegram_vienna_delivery.py
git commit -m "feat: add at-most-once co-op delivery helper"
```

## Task 3: Add Non-Expiring Source Claims to MongoDB

**Files:**
- Modify: `Project/Integration/mongodb_handler.py`
- Modify: `tests/test_telegram_vienna_delivery.py`

- [ ] **Step 1: Add failing route-query tests.**

Add tests proving source channels are accepted and do not write/use an expiry:

```python
def test_source_claim_excludes_existing_claims_without_expiry():
    collection = Mock()
    collection.find_one_and_update.return_value = {"_id": "claimed"}
    mongo = MongoDBHandler.__new__(MongoDBHandler)
    mongo.collection = collection

    assert mongo.claim_listing_delivery(
        "https://example.test/coop", "", "coop",
        claim_token="token", lease_seconds=None,
    ) is True
    query, update = collection.find_one_and_update.call_args.args[:2]
    state = next(part for part in query["$and"] if "telegram_delivery.coop.state" in part)
    assert state == {"telegram_delivery.coop.state": {"$nin": ["sent", "uncertain", "claimed"]}}
    assert "claim_until" not in update["$set"]
```

- [ ] **Step 2: Run the test and verify it fails.**

```bash
pytest -q tests/test_telegram_vienna_delivery.py::test_source_claim_excludes_existing_claims_without_expiry
```

Expected: failure because `coop` is not an allowed channel and the current
claim method always emits a lease.

- [ ] **Step 3: Implement route-aware claim behavior.**

Change `LISTING_DELIVERY_CHANNELS` to include `"coop"` and
`"private_coop"`. Keep existing Vienna behavior unchanged. For source routes:

- accept `lease_seconds=None`;
- query state with `$nin: ["sent", "uncertain", "claimed"]`;
- omit `claim_until` from the update;
- keep `claimed_at` and `claim_token` so success/quarantine can authenticate;
- never make source claims eligible through an expiry predicate.

For Vienna, retain the current 300-second lease and existing state query. Keep
`mark_listing_delivery_sent()` and `quarantine_listing_delivery()` compatible
with both route types; only unset `claim_until` when it exists.

- [ ] **Step 4: Run delivery state tests.**

```bash
pytest -q tests/test_telegram_vienna_delivery.py -k 'delivery or claim'
```

Expected: all Vienna and new source-route state tests pass.

- [ ] **Step 5: Commit MongoDB route support.**

```bash
git add Project/Integration/mongodb_handler.py tests/test_telegram_vienna_delivery.py
git commit -m "feat: add permanent co-op delivery claims"
```

## Task 4: Route Fast-Poll Only Through New Candidates

**Files:**
- Modify: `Project/run_coop.py`
- Modify: `Project/Tests/test_run_coop.py`

- [ ] **Step 1: Add failing fast-poll tests.**

Add tests that use a new qualifying listing and an existing qualifying listing:

```python
def test_source_feed_uses_new_candidates_not_full_seen_inventory():
    handler = _mongo_mock()
    new_listing = _l(url="https://mygewo.at/new", area_m2=75.0, rooms=3)
    old_listing = _l(url="https://mygewo.at/old", area_m2=90.0, rooms=4)
    handler.get_listings_by_urls.return_value = {old_listing.url: {"url": old_listing.url}}
    bot = MagicMock()
    bot.send_message.return_value = True

    with patch("run_coop.MongoDBHandler", return_value=handler), \
            patch("run_coop.poll_source", return_value=[new_listing, old_listing]), \
            patch("run_coop.TelegramBot", return_value=bot), \
            patch("run_coop.validate_url", return_value=True), \
            patch.dict(os.environ, {"TELEGRAM_MAIN_BOT_TOKEN": "t", "TELEGRAM_COOP_CHANNEL_ID": "c"}), \
            patch.dict(run_coop.coop.SOURCES, {"T": {"url": "u", "parser": "p"}}, clear=True):
        assert run_coop.run(no_send=False) == 0

    bot.send_message.assert_called_once()
    assert new_listing.url in bot.send_message.call_args.args[0]


def test_source_feed_rejects_small_coop_listing_before_sender():
    handler = _mongo_mock()
    listing = _l(url="https://mygewo.at/small", area_m2=74.99, rooms=3)
    bot = MagicMock()
    bot.send_message.return_value = True

    with patch("run_coop.MongoDBHandler", return_value=handler), \
            patch("run_coop.poll_source", return_value=[listing]), \
            patch("run_coop.TelegramBot", return_value=bot), \
            patch("run_coop.validate_url", return_value=True), \
            patch.dict(os.environ, {"TELEGRAM_MAIN_BOT_TOKEN": "t", "TELEGRAM_COOP_CHANNEL_ID": "c"}), \
            patch.dict(run_coop.coop.SOURCES, {"T": {"url": "u", "parser": "p"}}, clear=True):
        assert run_coop.run(no_send=False) == 0

    bot.send_message.assert_not_called()
```

Update send-path fixtures that are intended to deliver to use `area_m2=75.0`
or higher; leave alert-matcher tests at 70 m² to prove their independent
configuration behavior.

- [ ] **Step 2: Run the new fast-poll tests and verify failure.**

```bash
cd Project
python -m pytest -q Tests/test_run_coop.py -k 'source_feed'
```

Expected: the old loop sends the full `seen` list or does not apply the shared
strict policy, so at least one new assertion fails.

- [ ] **Step 3: Select candidates before upsert and deliver through helper.**

In `run()`:

1. Keep `mygewo_existing` and `new_alert_candidates()` before detail resolution.
2. Assign its result to `source_channel_candidates` while preserving the same
   candidate list passed to `deliver_user_alerts()`.
3. Replace the final `for listing in seen` source-send loop with
   `for listing in source_channel_candidates`.
4. Keep `is_coop_listing()` and configured `matches_coop_alerts()` before the
   shared helper so user-alert/source classification remains unchanged.
5. Select route `private_coop` for `coop_kind == "private_transfer"`, otherwise
   `coop`, and call:

```python
if send_coop_listing(
        listing,
        bots.get(getattr(listing, "coop_kind", None) or "mygewo"),
        handler,
        route_name,
        url_validator=validate_url,
        message_formatter=format_coop_message,
):
    sent += 1
```

The helper must not be called when no bot exists. Keep no-send mode from doing
candidate lookup or source delivery, matching existing dry-run tests.

- [ ] **Step 4: Run fast-poll tests.**

```bash
cd Project
python -m pytest -q Tests/test_run_coop.py
```

Expected: all fast-poll tests pass, including unchanged user-alert and upsert
ordering tests.

- [ ] **Step 5: Commit fast-poll integration.**

```bash
git add Project/run_coop.py Project/Tests/test_run_coop.py
git commit -m "fix: send only new qualifying co-op listings"
```

## Task 5: Route Daily Crawl Co-op Posts Through New-Only Delivery

**Files:**
- Modify: `Project/Application/main.py`
- Modify: `tests/test_telegram_vienna_delivery.py`

- [ ] **Step 1: Add failing main-route regression tests.**

Add a helper-level test for the pre-save URL map and an execution-level test:

```python
def test_main_coop_candidates_exclude_existing_urls_and_lookup_errors():
    from Application import main as main_module

    existing = Listing(url="https://example.test/old", source=Source.GENOSSENSCHAFT,
                       is_genossenschaft=True, coop_source="bautraeger_direct",
                       area_m2=90.0, rooms=4.0)
    fresh = Listing(url="https://example.test/new", source=Source.GENOSSENSCHAFT,
                    is_genossenschaft=True, coop_source="bautraeger_direct",
                    area_m2=90.0, rooms=4.0)
    mongo = Mock()
    mongo.get_listings_by_urls.return_value = {existing.url: {"url": existing.url}}

    assert main_module.new_coop_candidates(mongo, [existing, fresh]) == [fresh]
    mongo.get_listings_by_urls.return_value = None
    assert main_module.new_coop_candidates(mongo, [fresh]) == []
```

The existing main execution test should be changed to `area_m2=75.0` and assert
the shared `claim_listing_delivery`/`mark_listing_delivery_sent` calls instead
of legacy `mark_sent`.

- [ ] **Step 2: Run the new main tests and verify failure.**

```bash
pytest -q tests/test_telegram_vienna_delivery.py -k 'main_coop_candidates or main_completes_coop'
```

Expected: failure because the main module has no `new_coop_candidates()` and
still sends via direct `send_message()` plus `mark_sent()`.

- [ ] **Step 3: Implement pre-save daily candidate selection.**

Add a small helper in `Project/Application/main.py`:

```python
def new_coop_candidates(mongo, listings):
    candidates = []
    seen_urls = set()
    for listing in listings:
        if (
            not listing.is_genossenschaft
            or listing.coop_source == "willhaben"
            or not listing.url
            or listing.url in seen_urls
        ):
            continue
        seen_urls.add(listing.url)
        candidates.append(listing)
    existing = mongo.get_listings_by_urls([listing.url for listing in candidates])
    if existing is None:
        logging.error("Could not determine new co-op listings; skipping source delivery")
        return []
    return [listing for listing in candidates if listing.url not in existing]
```

Build `coop_broadcast_candidates = new_coop_candidates(mongo, all_listings)`
before `save_listings_to_mongodb(all_listings)`. Remove the old seven-day
`was_listing_sent_recently()` gate from this source route. Keep scoring and
storage for every listing.

- [ ] **Step 4: Replace direct daily source sends.**

Keep the existing same-run `compute_xsrc_fingerprint` collapse. Remove the
standalone daily URL-validation loop; the shared helper performs
`validate_url()` immediately before the claim. Call `send_coop_listing()` for
each collapsed candidate using route `"coop"`, `coop_bot`, and the existing
`format_coop_message`/`validate_url` dependencies. Do not call `send_message()`
or `mark_sent()` directly from `main.py`.

- [ ] **Step 5: Run main focused tests.**

```bash
pytest -q tests/test_telegram_vienna_delivery.py tests/test_telegram_vienna_config.py
python -m py_compile Project/Application/main.py Project/run_coop.py
```

Expected: all focused tests pass and both modules compile.

- [ ] **Step 6: Commit daily-crawl integration.**

```bash
git add Project/Application/main.py tests/test_telegram_vienna_delivery.py
git commit -m "fix: deduplicate daily co-op Telegram posts"
```

## Task 6: Full Verification and Review

**Files:**
- Modify only if a test exposes a concrete regression in the implementation above.

- [ ] **Step 1: Run focused vertical verification.**

```bash
pytest -q tests/test_telegram_vienna_delivery.py tests/test_telegram_vienna_config.py
cd Project && python -m pytest -q Tests/test_run_coop.py
```

Expected: all focused tests pass; no live network or MongoDB is contacted.

- [ ] **Step 2: Run the repository test command.**

```bash
cd Tests && python run_tests.py
```

Expected: existing suite passes or any pre-existing failure is recorded with
the exact test name and unchanged failure reason.

- [ ] **Step 3: Inspect the complete diff and invariants.**

```bash
git status --short
git diff --check HEAD~5..HEAD
git diff --stat HEAD~5..HEAD
git diff HEAD~5..HEAD -- Project/Application/main.py Project/Application/telegram_delivery.py Project/Integration/mongodb_handler.py Project/run_coop.py
```

Confirm `run_top5.py`, user-alert delivery, Vienna delivery, and message format
were not changed. Confirm every source Telegram send has a pre-send claim and
no source claim has an expiry predicate.

- [ ] **Step 4: Run independent code review.**

Review for duplicate paths, filter bypasses, fail-open MongoDB behavior, and
tests that only inspect source text. Resolve all concrete findings before
completion.

- [ ] **Step 5: Update the code graph.**

```bash
graphify update .
```

Inspect graph status and include generated graph files only if the project
tracks them and they are the direct result of this update.

- [ ] **Step 6: Commit graph output if required and verify clean status.**

```bash
git status --short
git add graphify-out
git commit -m "chore: update code graph"
git status --short
```

Expected: only intended source, test, spec/plan, and graph commits exist; no
secrets, `.env`, config credentials, or temporary HTML files are staged.
