# Vienna Telegram Filtered Feed Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans (recommended for inline execution). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route main-crawl property notifications to explicit `telegram_vienna` only when they meet the 75 m², 3-room, score, and URL gates, with permanent MongoDB-backed deduplication.

**Architecture:** Add a small delivery module for pure Vienna eligibility, same-run identity deduplication, and delivery orchestration. Add atomic route-specific state methods to `MongoDBHandler`; preserve those fields during ordinary and co-op document replacement. Keep crawl criteria, co-op routing, `run_top5.py`, and Telegram message formatting unchanged.

**Tech Stack:** Python 3.11, PyMongo, existing `TelegramBot`, pytest/unittest, `graphify update`.

---

## File Map

| File | Action | Responsibility |
| --- | --- | --- |
| `Project/Application/telegram_delivery.py` | Create | Vienna constants, numeric filter, identity keys, state-preserving copy, delivery loop. |
| `Project/Integration/mongodb_handler.py` | Modify | Atomic claim/release/mark/quarantine methods and co-op replacement state preservation. |
| `Project/Application/main.py` | Modify | Resolve Vienna credentials, remove seven-day raw check, invoke Vienna delivery, stop summary/no-result sends. |
| `Project/Application/helpers/utils.py` | Modify | Do not alias no-config Vienna credentials to main credentials. |
| `Project/setup_vienna_channel.py` | Modify | Write explicit channel under `telegram_vienna`. |
| `README.md` | Modify | Document Vienna credentials as explicit, not main fallback. |
| `tests/test_telegram_vienna_delivery.py` | Create | Pure policy, routing, state transition, URL, and same-run dedup regression tests. |
| `tests/test_telegram_vienna_config.py` | Create | Explicit config and no-main-fallback regression tests. |

## Task 1: Add Failing Vienna Policy Tests

**Files:**
- Create: `tests/test_telegram_vienna_delivery.py`
- Create: `Project/Application/telegram_delivery.py` in the next step

- [ ] **Step 1: Write boundary tests before implementation**

Create focused fixtures and tests. Keep all network and MongoDB behavior mocked:

```python
import math
from unittest.mock import Mock

from Application.telegram_delivery import (
    VIENNA_CHANNEL,
    VIENNA_MIN_AREA_M2,
    VIENNA_MIN_ROOMS,
    vienna_filter_reason,
)


def listing(**overrides):
    value = {
        "url": "https://example.test/listing-1",
        "title": "Testwohnung",
        "area_m2": 75.0,
        "rooms": 3.0,
        "score": 41.0,
    }
    value.update(overrides)
    return value


def test_vienna_constants_are_minimums():
    assert VIENNA_CHANNEL == "vienna"
    assert VIENNA_MIN_AREA_M2 == 75.0
    assert VIENNA_MIN_ROOMS == 3.0


def test_area_and_rooms_boundaries():
    assert vienna_filter_reason(listing(area_m2=74.99), 41.0, 40.0)
    assert vienna_filter_reason(listing(area_m2=75.0), 41.0, 40.0) is None
    assert vienna_filter_reason(listing(rooms=2.99), 41.0, 40.0)
    assert vienna_filter_reason(listing(rooms=3.0), 41.0, 40.0) is None


def test_missing_invalid_and_non_finite_filter_values_fail_closed():
    for value in (None, "75", "three", math.nan, math.inf, -math.inf):
        assert vienna_filter_reason(listing(area_m2=value), 41.0, 40.0)
        assert vienna_filter_reason(listing(rooms=value), 41.0, 40.0)


def test_score_must_be_strictly_above_existing_threshold():
    assert vienna_filter_reason(listing(), 40.0, 40.0)
    assert vienna_filter_reason(listing(), 40.01, 40.0) is None


def test_url_is_required_before_delivery():
    assert vienna_filter_reason(listing(url=None), 41.0, 40.0)
```

- [ ] **Step 2: Run the focused tests and verify they fail**

Run:

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter-telegram-dedup
pytest -q tests/test_telegram_vienna_delivery.py
```

Expected: collection fails because `Application.telegram_delivery` does not exist yet.

- [ ] **Step 3: Commit the failing-test checkpoint**

```bash
git add tests/test_telegram_vienna_delivery.py
git commit -m "test: define Vienna Telegram filter boundaries"
```

## Task 2: Implement Pure Policy and Delivery Helpers

**Files:**
- Create: `Project/Application/telegram_delivery.py`
- Test: `tests/test_telegram_vienna_delivery.py`

- [ ] **Step 1: Add policy constants and mapping conversion**

Implement the smallest pure API needed by the tests and main orchestration:

```python
import logging
import math
from dataclasses import asdict, is_dataclass
from typing import Any, Callable, Dict, Iterable, Mapping, Optional, Set, Tuple

from Application.helpers.listing_validator import compute_content_fingerprint, validate_url

logger = logging.getLogger(__name__)

VIENNA_CHANNEL = "vienna"
VIENNA_MIN_AREA_M2 = 75.0
VIENNA_MIN_ROOMS = 3.0
DELIVERY_STATE_FIELDS = (
    "telegram_delivery",
    "sent_to_telegram",
    "sent_to_telegram_at",
    "url_is_valid",
)


def listing_dict(listing: Any) -> Dict[str, Any]:
    if isinstance(listing, Mapping):
        return dict(listing)
    if is_dataclass(listing):
        return asdict(listing)
    if hasattr(listing, "__dict__"):
        return dict(vars(listing))
    return dict(listing)


def _finite_number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def vienna_filter_reason(
    listing: Mapping[str, Any], score: Any, score_threshold: Any
) -> Optional[str]:
    """Return a skip reason, or None when listing passes Vienna policy."""
    url = listing.get("url")
    if not isinstance(url, str) or not url.strip():
        return "missing URL"

    area = _finite_number(listing.get("area_m2"))
    if area is None or area < VIENNA_MIN_AREA_M2:
        return f"area below {VIENNA_MIN_AREA_M2:g} m2 or unknown"

    rooms = _finite_number(listing.get("rooms"))
    if rooms is None or rooms < VIENNA_MIN_ROOMS:
        return f"rooms below {VIENNA_MIN_ROOMS:g} or unknown"

    score_value = _finite_number(score)
    threshold = _finite_number(score_threshold)
    if score_value is None or threshold is None or score_value <= threshold:
        return "score at or below threshold"
    return None


def delivery_keys(listing: Mapping[str, Any]) -> Tuple[str, ...]:
    """Return URL/content keys used for same-run duplicate suppression."""
    url = str(listing.get("url") or "").strip()
    fingerprint = compute_content_fingerprint(dict(listing))
    return tuple(key for key in (f"url:{url}", f"content:{fingerprint}") if key)


def preserve_delivery_state(existing: Mapping[str, Any], replacement: Mapping[str, Any]) -> Dict[str, Any]:
    """Carry send/URL state across a scrape replacement."""
    result = dict(replacement)
    for field in DELIVERY_STATE_FIELDS:
        if field in existing:
            result[field] = existing[field]
    return result
```

- [ ] **Step 2: Add the delivery loop after the pure helpers**

Use the existing URL validator and only call the sender after a durable claim:

```python
def send_vienna_listings(
    listings: Iterable[Any],
    bot: Any,
    mongo: Any,
    url_validator: Callable[[str], bool] = validate_url,
) -> int:
    sent_count = 0
    seen_keys: Set[str] = set()
    threshold = getattr(bot, "min_score_threshold", 40)

    for raw_listing in listings:
        data = listing_dict(raw_listing)
        score = data.get("score")
        reason = vienna_filter_reason(data, score, threshold)
        if reason:
            logger.info("Skipping Vienna Telegram listing %s: %s", data.get("url"), reason)
            continue

        keys = delivery_keys(data)
        if not keys or any(key in seen_keys for key in keys):
            logger.info("Skipping same-run Vienna duplicate: %s", data.get("url"))
            continue
        seen_keys.update(keys)

        url = data["url"].strip()
        fingerprint = compute_content_fingerprint(data)
        if not url_validator(url):
            logger.warning("Skipping Vienna Telegram listing with invalid URL: %s", url)
            mongo.mark_url_invalid(url)
            continue

        if not mongo.claim_listing_delivery(url, fingerprint, VIENNA_CHANNEL):
            logger.info("Skipping already claimed/sent Vienna listing: %s", url)
            continue

        try:
            success = bool(bot.send_property_notification(data))
        except Exception:
            logger.exception("Vienna Telegram send failed for %s", url)
            success = False

        if not success:
            mongo.release_listing_delivery(url, fingerprint, VIENNA_CHANNEL)
            continue

        if mongo.mark_listing_delivery_sent(url, fingerprint, VIENNA_CHANNEL):
            sent_count += 1
            continue

        # Telegram confirmed delivery, but MongoDB did not record it. Keep the
        # candidate non-retryable if the quarantine update succeeds.
        if not mongo.quarantine_listing_delivery(url, fingerprint, VIENNA_CHANNEL):
            logger.error("Vienna delivery state uncertain and could not be quarantined: %s", url)

    return sent_count
```

- [ ] **Step 3: Run focused policy tests and verify they pass**

Run:

```bash
pytest -q tests/test_telegram_vienna_delivery.py
```

Expected: all policy tests pass.

- [ ] **Step 4: Commit the pure delivery module**

```bash
git add Project/Application/telegram_delivery.py tests/test_telegram_vienna_delivery.py
git commit -m "feat: add Vienna Telegram delivery policy"
```

## Task 3: Add Atomic MongoDB Route State

**Files:**
- Modify: `Project/Integration/mongodb_handler.py` after the existing `mark_sent()` helpers
- Test: `tests/test_telegram_vienna_delivery.py`

- [ ] **Step 1: Add failing state-transition tests**

Use a `MongoDBHandler.__new__()` instance with a mocked collection. Assert the
public methods and update payloads, not private MongoDB implementation details:

```python
from unittest.mock import ANY, Mock, patch
from Integration.mongodb_handler import MongoDBHandler


def handler_with_collection(*claim_results):
    handler = MongoDBHandler.__new__(MongoDBHandler)
    handler.collection = Mock()
    handler.collection.find_one_and_update.side_effect = claim_results
    handler.collection.update_one.return_value = Mock(modified_count=1)
    return handler


def test_claim_allows_one_winner_and_blocks_missing_result():
    handler = handler_with_collection(object(), None)
    assert handler.claim_listing_delivery("url", "fp", "vienna") is True
    assert handler.claim_listing_delivery("url", "fp", "vienna") is False
    query = handler.collection.find_one_and_update.call_args_list[0].args[0]
    assert {"url": "url"} in query["$and"][0]["$or"]
    assert {"content_fingerprint": "fp"} in query["$and"][0]["$or"]
    assert query["$and"][1] == {
        "telegram_delivery.vienna.state": {"$nin": ["sent", "uncertain"]}
    }
    assert {"telegram_delivery.vienna.claim_until": {"$lte": ANY}} in query["$and"][2]["$or"]


def test_release_and_mark_update_route_state():
    handler = handler_with_collection(object())
    assert handler.release_listing_delivery("url", "fp", "vienna") is True
    assert handler.mark_listing_delivery_sent("url", "fp", "vienna") is True
    updates = [call.args[1] for call in handler.collection.update_one.call_args_list]
    assert "$unset" in updates[0]
    assert updates[1]["$set"]["telegram_delivery.vienna.state"] == "sent"
    assert updates[1]["$set"]["sent_to_telegram"] is True


def test_quarantine_marks_uncertain_state():
    handler = handler_with_collection(object())
    assert handler.quarantine_listing_delivery("url", "fp", "vienna") is True
    update = handler.collection.update_one.call_args.args[1]
    assert update["$set"]["telegram_delivery.vienna.state"] == "uncertain"
```

- [ ] **Step 2: Run the state tests and verify failure**

Run:

```bash
pytest -q tests/test_telegram_vienna_delivery.py -k 'claim or release or mark or quarantine'
```

Expected: FAIL with missing `MongoDBHandler` delivery methods.

- [ ] **Step 3: Implement the atomic state methods**

Add an allowlist and methods using float timestamps, `$and` to avoid duplicate
`$or` keys, and the existing PyMongo error-handling style:

```python
LISTING_DELIVERY_CHANNELS = {"vienna"}


def _listing_delivery_query(url: str, fingerprint: str, prefix: str) -> Dict:
    identity = [{"url": url}]
    if fingerprint:
        identity.append({"content_fingerprint": fingerprint})
    return {
        "$and": [
            {"$or": identity},
            {f"{prefix}.state": {"$nin": ["sent", "uncertain"]}},
            {"$or": [
                {f"{prefix}.claim_until": {"$exists": False}},
                {f"{prefix}.claim_until": None},
                {f"{prefix}.claim_until": {"$lte": time.time()}},
            ]},
        ]
    }


def _validate_listing_delivery_channel(channel: str) -> str:
    if channel not in LISTING_DELIVERY_CHANNELS:
        raise ValueError(f"unknown listing delivery channel: {channel}")
    return f"telegram_delivery.{channel}"


def claim_listing_delivery(self, url: str, fingerprint: str,
                           channel: str = "vienna", lease_seconds: int = 300) -> bool:
    if self.collection is None or not url:
        return False
    prefix = _validate_listing_delivery_channel(channel)
    now = time.time()
    try:
        row = self.collection.find_one_and_update(
            _listing_delivery_query(url, fingerprint, prefix),
            {"$set": {
                f"{prefix}.state": "claimed",
                f"{prefix}.claimed_at": now,
                f"{prefix}.claim_until": now + lease_seconds,
            }},
            return_document=pymongo.ReturnDocument.AFTER,
        )
        return row is not None
    except Exception as exc:
        logger.error("MongoDB listing delivery claim failed: %s", exc)
        return False


def release_listing_delivery(self, url: str, fingerprint: str,
                             channel: str = "vienna") -> bool:
    prefix = _validate_listing_delivery_channel(channel)
    try:
        result = self.collection.update_one(
            {"$and": [
                {"$or": [{"url": url}, {"content_fingerprint": fingerprint}]},
                {f"{prefix}.state": "claimed"},
            ]},
            {"$set": {f"{prefix}.state": "failed"},
             "$unset": {f"{prefix}.claim_until": "", f"{prefix}.claimed_at": ""}},
        )
        return result.modified_count > 0
    except Exception as exc:
        logger.error("MongoDB listing delivery release failed: %s", exc)
        return False


def mark_listing_delivery_sent(self, url: str, fingerprint: str,
                               channel: str = "vienna") -> bool:
    prefix = _validate_listing_delivery_channel(channel)
    now = time.time()
    try:
        result = self.collection.update_one(
            {"$and": [
                {"$or": [{"url": url}, {"content_fingerprint": fingerprint}]},
                {f"{prefix}.state": "claimed"},
            ]},
            {"$set": {
                f"{prefix}.state": "sent",
                f"{prefix}.sent_at": now,
                "sent_to_telegram": True,
                "sent_to_telegram_at": now,
            }, "$unset": {f"{prefix}.claim_until": ""}},
        )
        return result.modified_count > 0
    except Exception as exc:
        logger.error("MongoDB listing delivery marker failed: %s", exc)
        return False


def quarantine_listing_delivery(self, url: str, fingerprint: str,
                                channel: str = "vienna") -> bool:
    prefix = _validate_listing_delivery_channel(channel)
    try:
        result = self.collection.update_one(
            {"$and": [
                {"$or": [{"url": url}, {"content_fingerprint": fingerprint}]},
                {f"{prefix}.state": "claimed"},
            ]},
            {"$set": {f"{prefix}.state": "uncertain",
                      f"{prefix}.uncertain_at": time.time()},
             "$unset": {f"{prefix}.claim_until": ""}},
        )
        return result.modified_count > 0
    except Exception as exc:
        logger.error("MongoDB listing delivery quarantine failed: %s", exc)
        return False
```

Bind the functions as methods on `MongoDBHandler` using the class's existing
method indentation and keep `_validate_listing_delivery_channel` private to
the module. The claim query must match either URL or fingerprint but must
reject route states `sent` and `uncertain`.

- [ ] **Step 4: Verify state tests and delivery tests pass**

Run:

```bash
pytest -q tests/test_telegram_vienna_delivery.py -k 'claim or release or mark or quarantine'
```

Expected: all selected tests pass.

- [ ] **Step 5: Commit MongoDB state support**

```bash
git add Project/Integration/mongodb_handler.py tests/test_telegram_vienna_delivery.py
git commit -m "feat: add atomic Vienna Telegram delivery state"
```

## Task 4: Preserve Delivery State During Listing Replacement

**Files:**
- Modify: `Project/Application/main.py:498-503`
- Modify: `Project/Integration/mongodb_handler.py:_replace_preserving_state()`
- Test: `tests/test_telegram_vienna_delivery.py`

- [ ] **Step 1: Add the failing replacement-preservation test**

```python
from Application.telegram_delivery import preserve_delivery_state


def test_listing_refresh_preserves_telegram_and_url_state():
    existing = {
        "telegram_delivery": {"vienna": {"state": "sent"}},
        "sent_to_telegram": True,
        "sent_to_telegram_at": 123.0,
        "url_is_valid": True,
    }
    replacement = {
        "title": "Fresh scrape",
        "telegram_delivery": {},
        "sent_to_telegram": False,
        "url_is_valid": None,
    }
    result = preserve_delivery_state(existing, replacement)
    assert result["telegram_delivery"] == existing["telegram_delivery"]
    assert result["sent_to_telegram"] is True
    assert result["sent_to_telegram_at"] == 123.0
    assert result["url_is_valid"] is True
    assert result["title"] == "Fresh scrape"
```

- [ ] **Step 2: Run the preservation test and verify failure**

Run:

```bash
pytest -q tests/test_telegram_vienna_delivery.py -k preserves
```

Expected: FAIL until the helper and replacement call sites are wired.

- [ ] **Step 3: Wire state preservation into ordinary listing replacement**

In `save_listings_to_mongodb()`, preserve state before `replace_one()`:

```python
if existing_by_url:
    listing_dict['_id'] = existing_by_url['_id']
    listing_dict = preserve_delivery_state(existing_by_url, listing_dict)
    collection.replace_one({"_id": existing_by_url['_id']}, listing_dict)
```

Import `preserve_delivery_state` with the other delivery helpers. In
`MongoDBHandler._replace_preserving_state()`, add `telegram_delivery` to the
existing state fields carried from the old co-op document:

```python
for k in (
    "sent_to_telegram",
    "sent_to_telegram_at",
    "telegram_delivery",
    "url_is_valid",
):
    if k in existing:
        listing[k] = existing[k]
```

- [ ] **Step 4: Run replacement and existing co-op tests**

Run:

```bash
pytest -q tests/test_telegram_vienna_delivery.py -k 'preserves'
pytest -q tests/test_upsert_coop.py tests/test_upsert_unit_fingerprint.py
```

Expected: all selected tests pass and existing co-op state remains preserved.

- [ ] **Step 5: Commit state preservation**

```bash
git add Project/Application/main.py Project/Integration/mongodb_handler.py \
  Project/Application/telegram_delivery.py tests/test_telegram_vienna_delivery.py
git commit -m "fix: preserve Telegram delivery state on listing refresh"
```

## Task 5: Make Vienna Credentials Explicit

**Files:**
- Modify: `Project/Application/helpers/utils.py:245-249`
- Modify: `Project/setup_vienna_channel.py:130-137`
- Modify: `README.md:45-50`
- Create: `tests/test_telegram_vienna_config.py`

- [ ] **Step 1: Write failing config tests**

```python
import os

from Application.helpers.utils import supplement_config_with_env_vars


def test_vienna_environment_values_are_explicit():
    config = {"telegram": {"telegram_main": {"bot_token": "main", "chat_id": "main-chat"}}}
    old = {
        key: os.environ.get(key)
        for key in ("TELEGRAM_BOT_VIENNA_TOKEN", "TELEGRAM_BOT_VIENNA_CHAT_ID")
    }
    try:
        os.environ["TELEGRAM_BOT_VIENNA_TOKEN"] = "vienna-token"
        os.environ["TELEGRAM_BOT_VIENNA_CHAT_ID"] = "vienna-chat"
        result = supplement_config_with_env_vars(config)
        assert result["telegram"]["telegram_vienna"] == {
            "bot_token": "vienna-token",
            "chat_id": "vienna-chat",
        }
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_main_credentials_do_not_create_vienna_destination():
    from Application.helpers import utils

    old_config = utils._config
    old_project_root = utils._project_root
    old = {
        key: os.environ.get(key)
        for key in (
            "TELEGRAM_MAIN_BOT_TOKEN",
            "TELEGRAM_MAIN_CHAT_ID",
            "TELEGRAM_BOT_VIENNA_TOKEN",
            "TELEGRAM_BOT_VIENNA_CHAT_ID",
        )
    }
    try:
        os.environ["TELEGRAM_MAIN_BOT_TOKEN"] = "main-token"
        os.environ["TELEGRAM_MAIN_CHAT_ID"] = "main-chat"
        os.environ.pop("TELEGRAM_BOT_VIENNA_TOKEN", None)
        os.environ.pop("TELEGRAM_BOT_VIENNA_CHAT_ID", None)
        utils._config = None
        utils._project_root = None
        result = utils.load_config()
        vienna = result.get("telegram", {}).get("telegram_vienna", {})
        assert vienna.get("bot_token") is None
        assert vienna.get("chat_id") is None
    finally:
        utils._config = old_config
        utils._project_root = old_project_root
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
```

- [ ] **Step 2: Run config tests and verify failure**

Run:

```bash
pytest -q tests/test_telegram_vienna_config.py
```

Expected: the no-config fallback test fails because current fallback code
copies main credentials into `telegram_vienna`.

- [ ] **Step 3: Remove fallback alias and update setup/documentation**

In the no-config branch of `load_config()`, replace the current fallback:

```python
telegram_vienna_token = os.getenv('TELEGRAM_BOT_VIENNA_TOKEN')
telegram_vienna_chat_id = os.getenv('TELEGRAM_BOT_VIENNA_CHAT_ID')
```

Keep the `telegram_vienna` object with explicit `None` values in the fallback
schema, never substitute main credentials:

```python
"telegram_vienna": {
    "bot_token": telegram_vienna_token,
    "chat_id": telegram_vienna_chat_id,
},
```

In
`setup_vienna_channel.py`, write:

```python
config['telegram']['telegram_vienna'] = {
    'bot_token': bot_token,
    'chat_id': channel_id,
}
```

Update README rows to say both Vienna variables are required for the Vienna
feed and have no main-channel default. Do not print or commit token values.

- [ ] **Step 4: Run config tests**

Run:

```bash
pytest -q tests/test_telegram_vienna_config.py tests/test_env_var_fallback.py
```

Expected: all selected tests pass. Existing main environment override tests
must remain green.

- [ ] **Step 5: Commit explicit destination configuration**

```bash
git add Project/Application/helpers/utils.py Project/setup_vienna_channel.py \
  README.md tests/test_telegram_vienna_config.py
git commit -m "fix: require explicit Vienna Telegram destination"
```

## Task 6: Wire Main Crawl to Vienna-Only Delivery

**Files:**
- Modify: `Project/Application/main.py:741-765,790-832,905-965`
- Test: `tests/test_telegram_vienna_delivery.py`

- [ ] **Step 1: Add delivery-loop and main-routing regression tests**

```python
from unittest.mock import ANY, Mock, patch
from Application.telegram_delivery import send_vienna_listings


def test_delivery_sends_only_valid_75m2_three_room_listing():
    bot = Mock(min_score_threshold=40.0)
    bot.send_property_notification.return_value = True
    mongo = Mock()
    mongo.claim_listing_delivery.return_value = True
    mongo.mark_listing_delivery_sent.return_value = True

    listings = [
        listing(url="https://example.test/good", score=41.0),
        listing(url="https://example.test/small", area_m2=74.99, score=99.0),
        listing(url="https://example.test/two", rooms=2.0, score=99.0),
    ]
    assert send_vienna_listings(listings, bot, mongo, lambda url: True) == 1
    assert bot.send_property_notification.call_count == 1
    assert bot.send_property_notification.call_args.args[0]["url"].endswith("good")


def test_failed_send_releases_claim_for_retry():
    bot = Mock(min_score_threshold=40.0)
    bot.send_property_notification.return_value = False
    mongo = Mock()
    mongo.claim_listing_delivery.return_value = True
    assert send_vienna_listings([listing()], bot, mongo, lambda url: True) == 0
    mongo.release_listing_delivery.assert_called_once_with(
        listing()["url"], ANY, "vienna"
    )
    mongo.mark_listing_delivery_sent.assert_not_called()


def test_marker_failure_quarantines_confirmed_send():
    bot = Mock(min_score_threshold=40.0)
    bot.send_property_notification.return_value = True
    mongo = Mock()
    mongo.claim_listing_delivery.return_value = True
    mongo.mark_listing_delivery_sent.return_value = False
    mongo.quarantine_listing_delivery.return_value = True
    assert send_vienna_listings([listing()], bot, mongo, lambda url: True) == 0
    mongo.quarantine_listing_delivery.assert_called_once()


def test_invalid_url_is_marked_and_never_sent():
    bot = Mock(min_score_threshold=40.0)
    mongo = Mock()
    assert send_vienna_listings(
        [listing(url="https://example.test/broken")], bot, mongo, lambda url: False
    ) == 0
    mongo.mark_url_invalid.assert_called_once_with("https://example.test/broken")
    mongo.claim_listing_delivery.assert_not_called()
    bot.send_property_notification.assert_not_called()


def test_same_url_or_content_is_sent_once():
    bot = Mock(min_score_threshold=40.0)
    bot.send_property_notification.return_value = True
    mongo = Mock()
    mongo.claim_listing_delivery.return_value = True
    mongo.mark_listing_delivery_sent.return_value = True
    first = listing(url="https://example.test/one")
    same_url = dict(first, title="Updated title")
    same_content = dict(first, url="https://example.test/two")
    assert send_vienna_listings(
        [first, same_url, same_content], bot, mongo, lambda url: True
    ) == 1
    bot.send_property_notification.assert_called_once()


def test_main_destination_resolver_never_falls_back_to_main():
    from Application.main import resolve_vienna_telegram_bot

    config = {
        "telegram": {
            "telegram_main": {"bot_token": "main", "chat_id": "main-chat"},
            "telegram_vienna": {"bot_token": "vienna", "chat_id": "vienna-chat"},
        }
    }
    with patch("Application.main.os.getenv", return_value=None), \
            patch("Application.main.TelegramBot") as telegram_bot:
        assert resolve_vienna_telegram_bot(config) is telegram_bot.return_value
        telegram_bot.assert_called_once_with("vienna", "vienna-chat")
        assert resolve_vienna_telegram_bot(
            {"telegram": {"telegram_main": {"bot_token": "main", "chat_id": "main-chat"}}}
        ) is None
```

- [ ] **Step 2: Run delivery tests and verify failure**

Run:

```bash
pytest -q tests/test_telegram_vienna_delivery.py -k 'delivery or invalid_url or same_url or main_destination'
```

Expected: the resolver test fails with a missing `resolve_vienna_telegram_bot`
function; the delivery-loop tests remain green from the earlier delivery-module
task.

- [ ] **Step 3: Add and test an explicit Vienna bot resolver**

Add this top-level helper to `Project/Application/main.py`. It has no fallback
to `telegram_main`, making the routing decision independently testable:

```python
def resolve_vienna_telegram_bot(config):
    telegram_config = config.get('telegram', {})
    vienna_config = telegram_config.get('telegram_vienna', {})
    vienna_token = os.getenv('TELEGRAM_BOT_VIENNA_TOKEN') or vienna_config.get('bot_token')
    vienna_chat_id = os.getenv('TELEGRAM_BOT_VIENNA_CHAT_ID') or vienna_config.get('chat_id')
    if vienna_token and vienna_chat_id:
        return TelegramBot(vienna_token, vienna_chat_id)
    return None
```

Use it in main while keeping `bot_main_token` for the existing co-op bot only:

Import the delivery entry point and state-preservation helper alongside the
existing application imports:

```python
from Application.telegram_delivery import (
    preserve_delivery_state,
    send_vienna_listings,
)
```

```python
telegram_bot = None
coop_bot = None
if send_to_telegram:
    telegram_config = config.get('telegram', {})
    telegram_bot = resolve_vienna_telegram_bot(config)
    if telegram_bot:
        logging.info("Telegram Vienna bot initialized for filtered property notifications")
    else:
        logging.warning("Vienna Telegram destination is not configured; property delivery disabled")

    # Existing co-op initialization remains based on main credentials.
    bot_main_token = os.getenv('TELEGRAM_MAIN_BOT_TOKEN') or telegram_config.get('telegram_main', {}).get('bot_token')
    coop_channel_id = os.getenv('TELEGRAM_COOP_CHANNEL_ID')
    if bot_main_token and coop_channel_id:
        coop_bot = TelegramBot(bot_main_token, coop_channel_id)
```

- [ ] **Step 4: Remove the seven-day raw query and retain scoring/storage**

Delete the `SEVEN_DAYS` block and its direct `mongo.collection.find_one()`
call. Keep the score calculation and append only non-co-op high-score listings:

```python
for listing in all_listings:
    if listing.is_genossenschaft and listing.coop_source != 'willhaben':
        coop_broadcast_candidates.append(listing)

    if telegram_bot:
        score = telegram_bot.calculate_listing_score(listing.__dict__)
        listing.score = score
        if listing.is_genossenschaft:
            logging.info("Co-op listing routed separately: %s", listing.title)
        elif score > telegram_bot.min_score_threshold:
            high_score_listings.append(listing)
    else:
        from Application.scoring import score_apartment_simple
        listing.score = score_apartment_simple(listing.__dict__)
```

Do not use a missing `telegram_bot` to suppress scores or persistence.

- [ ] **Step 5: Replace the property-send loop with the delivery module**

After `save_listings_to_mongodb(all_listings)` and after the existing co-op
broadcast, replace the old per-listing send/`mark_sent()` loop with:

```python
if send_to_telegram and telegram_bot and high_score_listings:
    telegram_sent_count = send_vienna_listings(
        high_score_listings,
        telegram_bot,
        mongo,
    )
    logging.info(
        "Vienna Telegram sent %d/%d qualifying candidates",
        telegram_sent_count,
        len(high_score_listings),
    )
elif send_to_telegram and not telegram_bot:
    logging.info("Vienna Telegram delivery skipped: destination unavailable")
```

Remove the summary and no-result `send_message()` blocks from this crawl path.
Leave informative local logs only. Do not alter `run_top5.py`.

- [ ] **Step 6: Run focused delivery and main-import tests**

Run:

```bash
pytest -q tests/test_telegram_vienna_delivery.py tests/test_telegram_vienna_config.py
python -m py_compile Project/Application/telegram_delivery.py \
  Project/Application/main.py Project/Integration/mongodb_handler.py
```

Expected: focused tests pass and compilation exits with status 0.

- [ ] **Step 7: Commit main integration**

```bash
git add Project/Application/main.py Project/Application/telegram_delivery.py \
  tests/test_telegram_vienna_delivery.py
git commit -m "feat: route filtered crawl notifications to Vienna Telegram"
```

## Task 7: Full Verification and Graph Update

**Files:**
- Modify: `graphify-out/` generated graph artifacts only after verification

- [ ] **Step 1: Run focused regression suite**

```bash
pytest -q tests/test_telegram_vienna_delivery.py tests/test_telegram_vienna_config.py
```

Expected: all focused tests pass with no network calls.

- [ ] **Step 2: Run the project test suite**

```bash
cd Project
python -m unittest discover -s ../tests -p 'test_*.py'
```

Expected: no new failures attributable to Vienna routing; record any
pre-existing failures with exact test names instead of masking them.

- [ ] **Step 3: Rebuild the knowledge graph**

```bash
cd /Users/vladbrincoveanu/Desktop/Startup/immo-scouter-telegram-dedup
graphify update .
```

Expected: graph update completes and includes `telegram_delivery.py` plus the
new `MongoDBHandler` delivery methods. Review generated graph changes before
staging them.

- [ ] **Step 4: Inspect the final diff and status**

```bash
git status --short
git diff --check
git diff HEAD~5..HEAD --stat
git log --oneline -10
```

Confirm no secrets, `.env` files, live channel IDs, generated test output, or
unrelated worktree changes are staged.

- [ ] **Step 5: Commit graph update if generated changes are relevant**

```bash
git add graphify-out
git commit -m "chore: update graph for Vienna Telegram delivery"
```

Only stage graph files produced by `graphify update`; do not stage unrelated
generated artifacts.

## Success Checklist

- [ ] Explicit `telegram_vienna` credentials are required; main is never used as a fallback.
- [ ] Vienna send gate requires valid URL, area >= 75 m², rooms >= 3, and score > configured threshold.
- [ ] Unknown and non-finite filter values fail closed.
- [ ] Same-run URL/content duplicates send once.
- [ ] MongoDB claim is atomic and permanent `sent`/`uncertain` states block reposts.
- [ ] Listing replacement preserves delivery and URL state.
- [ ] Telegram failure releases claim; confirmed send marks state; marker uncertainty is quarantined.
- [ ] Main crawl emits listings only, not summaries/no-result notices.
- [ ] Co-op routing and `run_top5.py` remain unchanged.
- [ ] Focused tests, full tests, syntax checks, and graph update are verified.
