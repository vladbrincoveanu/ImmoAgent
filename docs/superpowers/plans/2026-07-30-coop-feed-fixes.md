# Co-op Feed Fixes (P0 + P1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the co-op feed actually deliver — real photos on `/coop` rows, and Telegram alerts that fire instead of silently disabling themselves.

**Architecture:** Two independent fixes on the existing mygewo poll. Photos gain a second hop: the extraction ladder already inside `_og_image()` is pointed at the Bauträger's own page instead of the mygewo offer page, guarded by a probe-version marker so the re-probe happens exactly once per unit. Telegram gains a router that picks a channel per `coop_kind` and fails loudly when a channel secret is absent.

**Tech Stack:** Python 3.11, BeautifulSoup, requests, MongoDB, GitHub Actions, Next.js 15 dashboard, Playwright.

**Spec:** `docs/superpowers/specs/2026-07-30-coop-private-alerts-design.md` (`ui_scope: true`, `test_scope: true`)

---

## File Structure

| File | Responsibility |
|---|---|
| `Project/Application/scraping/genossenschaft_scraper.py` | Add `resolve_builder_image()` — one function, ~25 lines. Everything else there is untouched. |
| `Project/run_coop.py` | Re-probe gating on `image_probe_v`; channel routing on send. |
| `Project/Application/coop_alert_router.py` | **New.** Maps a listing to its Telegram chat id. |
| `Project/Tests/test_coop_images.py` | Extend — builder-page hop, all four measured builder shapes. |
| `Project/Tests/test_run_coop.py` | Extend — re-probe fires once, then never again. |
| `Project/Tests/test_coop_alert_router.py` | **New.** Routing + missing-secret behaviour. |
| `.github/workflows/coop-fast-poll.yml` | Cadence (2 min, 06:00–17:00 Vienna) + new secret env. |

---

### Task 1: Builder-page image hop

**Files:**
- Modify: `Project/Application/scraping/genossenschaft_scraper.py` (append after `resolve_offer_details`, ~line 684)
- Test: `Project/Tests/test_coop_images.py`

- [ ] **Step 1: Write the failing tests**

Append to `Project/Tests/test_coop_images.py`:

```python
# --- T4: builder-page hop -----------------------------------------------------

from unittest.mock import patch  # noqa: E402

from Application.scraping.genossenschaft_scraper import (  # noqa: E402
    resolve_builder_image,
)

_LEBENSWERT = (
    '<html><head><meta property="og:image" '
    'content="https://storage.justimmo.at/thumb/abc/fc_h1080/XezxUq.jpg"/>'
    '</head><body></body></html>'
)
_FRIEDEN = (
    '<html><head><meta data-react-helmet="true" property="og:image" '
    'content="https://portego.frieden.at/PublicFile/jVjKAN5jy5"/>'
    '</head><body></body></html>'
)
# gesiba/nhg publish no og:image — the <img> ladder inside _og_image must carry these.
_GESIBA = (
    '<html><head></head><body>'
    '<img src="/assets/logo.svg"/>'
    '<img src="/media/objekte/010001418110016/wohnzimmer.jpg"/>'
    '</body></html>'
)
_NO_PHOTO = '<html><head></head><body><img src="/assets/icon-menu.svg"/></body></html>'


def test_builder_image_from_og_image():
    with patch("Application.scraping.genossenschaft_scraper.fetch",
               return_value=_LEBENSWERT):
        assert resolve_builder_image("https://www.lebenswert-wohnen.at/objekt/7769786") == \
            "https://storage.justimmo.at/thumb/abc/fc_h1080/XezxUq.jpg"


def test_builder_image_from_helmet_og_image():
    with patch("Application.scraping.genossenschaft_scraper.fetch",
               return_value=_FRIEDEN):
        assert resolve_builder_image("https://www.frieden.at/immobiliensuche/1840") == \
            "https://portego.frieden.at/PublicFile/jVjKAN5jy5"


def test_builder_image_falls_back_to_content_img_when_no_og():
    with patch("Application.scraping.genossenschaft_scraper.fetch",
               return_value=_GESIBA):
        got = resolve_builder_image("https://www.gesiba.at/immobilien/wohnungen/detail")
    assert got is not None and got.endswith("/wohnzimmer.jpg")
    assert "logo" not in got


def test_builder_image_none_when_only_icons():
    with patch("Application.scraping.genossenschaft_scraper.fetch",
               return_value=_NO_PHOTO):
        assert resolve_builder_image("https://www.nhg.at/Projekte/Details/?id=610") is None


def test_builder_image_none_on_fetch_failure():
    with patch("Application.scraping.genossenschaft_scraper.fetch",
               side_effect=Exception("boom")):
        assert resolve_builder_image("https://dead.example.at/x") is None


def test_builder_image_none_for_empty_url():
    assert resolve_builder_image("") is None
    assert resolve_builder_image(None) is None
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd Project/Tests && python -m pytest test_coop_images.py -k builder_image -v
```
Expected: FAIL — `ImportError: cannot import name 'resolve_builder_image'`

- [ ] **Step 3: Write minimal implementation**

Append to `Project/Application/scraping/genossenschaft_scraper.py`:

```python
def resolve_builder_image(builder_url: Optional[str]) -> Optional[str]:
    """One fetch of a Bauträger's own page → a unit photo URL, or None.

    mygewo's /angebot/ pages carry no unit photo (measured: every unit resolved
    to "" under the old probe), but the builder pages they link to often do —
    2 of 4 sampled builders expose og:image, and the rest expose a usable <img>.
    The whole extraction ladder already lives in `_og_image`; this only points it
    at the builder page. Never raises: one dead builder site must not abort a poll."""
    if not builder_url:
        return None
    try:
        html = fetch(builder_url)
    except Exception as e:
        logger.warning(f"builder-page fetch failed for {builder_url}: {e}")
        return None
    return _og_image(html)
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd Project/Tests && python -m pytest test_coop_images.py -k builder_image -v
```
Expected: PASS — 6 passed

- [ ] **Step 5: Run the whole image suite for regressions**

```
cd Project/Tests && python -m pytest test_coop_images.py -v
```
Expected: PASS — all pre-existing tests still green

- [ ] **Step 6: Commit**

```
git add Project/Application/scraping/genossenschaft_scraper.py Project/Tests/test_coop_images.py
git commit -m "feat(coop): resolve unit photos from the builder page"
```

---

### Task 2: One-shot re-probe gated on `image_probe_v`

`""` is currently terminal and every unit already holds it. Without a version
marker, resetting `"" → None` re-probes forever for every builder that genuinely
has no photo. With it, each unit is re-probed exactly once under the new resolver.

**Files:**
- Modify: `Project/run_coop.py:196-220` (the `for listing in seen:` detail-fetch block)
- Test: `Project/Tests/test_run_coop.py`

- [ ] **Step 1: Write the failing tests**

Append to `Project/Tests/test_run_coop.py`:

```python
IMAGE_PROBE_V = 2


def test_unit_with_old_probe_version_is_reprobed_once(monkeypatch):
    """A unit carrying the poisoned "" from the v1 probe gets exactly one retry."""
    calls = []

    def fake_resolve(url):
        calls.append(url)
        return "https://cdn.builder.at/a.jpg"

    stored = {"builder_url": "https://www.gesiba.at/x", "image_url": "",
              "image_probe_v": 1}
    got = maybe_reprobe_image(stored, fake_resolve)
    assert got["image_url"] == "https://cdn.builder.at/a.jpg"
    assert got["image_probe_v"] == IMAGE_PROBE_V
    assert len(calls) == 1


def test_unit_at_current_probe_version_is_not_refetched():
    """Terminal within a version: no photo found stays no photo, no request."""
    calls = []

    def fake_resolve(url):
        calls.append(url)
        return "should-not-be-used"

    stored = {"builder_url": "https://www.nhg.at/x", "image_url": "",
              "image_probe_v": IMAGE_PROBE_V}
    got = maybe_reprobe_image(stored, fake_resolve)
    assert got["image_url"] == ""
    assert calls == []


def test_reprobe_miss_is_terminal_at_new_version():
    """A v2 miss records "" and bumps the version, so it never retries again."""
    stored = {"builder_url": "https://www.nhg.at/x", "image_url": "",
              "image_probe_v": 1}
    got = maybe_reprobe_image(stored, lambda url: None)
    assert got["image_url"] == ""
    assert got["image_probe_v"] == IMAGE_PROBE_V


def test_reprobe_skipped_without_builder_url():
    """No builder page to hop to — nothing to do, and no version bump."""
    calls = []
    stored = {"builder_url": None, "image_url": "", "image_probe_v": 1}
    got = maybe_reprobe_image(stored, lambda url: calls.append(url))
    assert calls == []
    assert got["image_probe_v"] == 1
```

Add the import at the top of the file, alongside the existing `run_coop` imports:

```python
from run_coop import maybe_reprobe_image  # noqa: E402
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd Project/Tests && python -m pytest test_run_coop.py -k reprobe -v
```
Expected: FAIL — `ImportError: cannot import name 'maybe_reprobe_image'`

- [ ] **Step 3: Write minimal implementation**

Add near `MAX_DETAIL_FETCHES_PER_RUN` in `Project/run_coop.py`:

```python
# Bumped whenever the photo-resolution strategy changes. v1 read og:image off the
# mygewo offer page, which never carries a unit photo, so every unit stored the
# terminal "". v2 hops to the builder's own page. A stored version below this one
# earns exactly one re-probe; after that "" is terminal again, which is what stops
# a photo-less builder from being re-fetched on all ~330 polls a day.
IMAGE_PROBE_V = 2


def maybe_reprobe_image(stored: dict, resolve) -> dict:
    """Re-probe one unit's photo if it predates the current probe version.

    Returns the fields to persist. `resolve` is injected so the poll can pass the
    real network call and tests can pass a stub."""
    out = dict(stored)
    if out.get("image_probe_v", 1) >= IMAGE_PROBE_V:
        return out
    if not out.get("builder_url"):
        return out
    # `or ""` is what makes a miss terminal within this version.
    out["image_url"] = resolve(out["builder_url"]) or ""
    out["image_probe_v"] = IMAGE_PROBE_V
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd Project/Tests && python -m pytest test_run_coop.py -k reprobe -v
```
Expected: PASS — 4 passed

- [ ] **Step 5: Wire it into the poll loop**

In the `for listing in seen:` block of `run()`, after the existing builder-url
resolution, add the re-probe under the same fetch cap:

```python
        stored = handler.get_listing(listing.url) or {}
        # Gate on the version BEFORE spending a fetch slot: units already at v2
        # must not consume the per-run budget that cold units need.
        if (stored.get("image_probe_v", 1) < IMAGE_PROBE_V
                and listing.builder_url
                and detail_fetches < MAX_DETAIL_FETCHES_PER_RUN):
            detail_fetches += 1
            probed = maybe_reprobe_image(
                {"builder_url": listing.builder_url,
                 "image_url": stored.get("image_url"),
                 "image_probe_v": stored.get("image_probe_v", 1)},
                coop.resolve_builder_image,
            )
            listing.image_url = probed["image_url"] or None
            listing.image_probe_v = probed["image_probe_v"]
```

`image_probe_v` must exist on the `Listing` dataclass or the assignment is lost
on upsert. Add it to `Project/Domain/listing.py` alongside `image_url`:

```python
    image_probe_v: Optional[int] = None
```

- [ ] **Step 6: Run the full co-op suite**

```
cd Project/Tests && python -m pytest test_run_coop.py test_coop_images.py test_upsert_coop.py -v
```
Expected: PASS, no regressions

- [ ] **Step 7: Commit**

```
git add Project/run_coop.py Project/Tests/test_run_coop.py
git commit -m "feat(coop): one-shot photo re-probe gated on image_probe_v"
```

---

### Task 3: Telegram channel router

**Files:**
- Create: `Project/Application/coop_alert_router.py`
- Test: `Project/Tests/test_coop_alert_router.py`

- [ ] **Step 1: Write the failing tests**

Create `Project/Tests/test_coop_alert_router.py`:

```python
"""Co-op alert routing: which Telegram channel a co-op hit goes to.

The bug this guards: TELEGRAM_COOP_CHANNEL_ID was never set, the workflow warned
non-fatally, and the poll ran green for weeks while sending nothing. A missing
channel must be visible, not inferred from silence."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from Application.coop_alert_router import route, missing_channels  # noqa: E402


def test_mygewo_unit_routes_to_coop_channel(monkeypatch):
    monkeypatch.setenv("TELEGRAM_COOP_CHANNEL_ID", "-100111")
    assert route("mygewo") == "-100111"


def test_private_transfer_routes_to_its_own_channel(monkeypatch):
    monkeypatch.setenv("TELEGRAM_COOP_CHANNEL_ID", "-100111")
    monkeypatch.setenv("TELEGRAM_PRIVATE_COOP_CHANNEL_ID", "-100222")
    assert route("private_transfer") == "-100222"


def test_private_transfer_does_not_fall_back_to_coop_channel(monkeypatch):
    """Urgent Ablöse hits must not be buried in the bulk mygewo feed."""
    monkeypatch.setenv("TELEGRAM_COOP_CHANNEL_ID", "-100111")
    monkeypatch.delenv("TELEGRAM_PRIVATE_COOP_CHANNEL_ID", raising=False)
    assert route("private_transfer") is None


def test_missing_channels_lists_every_unset_secret(monkeypatch):
    monkeypatch.delenv("TELEGRAM_COOP_CHANNEL_ID", raising=False)
    monkeypatch.delenv("TELEGRAM_PRIVATE_COOP_CHANNEL_ID", raising=False)
    assert set(missing_channels()) == {
        "TELEGRAM_COOP_CHANNEL_ID", "TELEGRAM_PRIVATE_COOP_CHANNEL_ID"}


def test_missing_channels_empty_when_all_set(monkeypatch):
    monkeypatch.setenv("TELEGRAM_COOP_CHANNEL_ID", "-100111")
    monkeypatch.setenv("TELEGRAM_PRIVATE_COOP_CHANNEL_ID", "-100222")
    assert missing_channels() == []
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd Project/Tests && python -m pytest test_coop_alert_router.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'Application.coop_alert_router'`

- [ ] **Step 3: Write minimal implementation**

Create `Project/Application/coop_alert_router.py`:

```python
"""Which Telegram channel a co-op hit belongs in.

Two feeds, deliberately not one: mygewo units arrive in bulk and are browsed,
while private Ablöse ads are first-come-first-served and are acted on within
minutes. Mixing them buries the urgent ones."""
import os
from typing import List, Optional

_CHANNEL_BY_KIND = {
    "mygewo": "TELEGRAM_COOP_CHANNEL_ID",
    "private_transfer": "TELEGRAM_PRIVATE_COOP_CHANNEL_ID",
}


def route(coop_kind: str) -> Optional[str]:
    """Chat id for this kind of co-op hit, or None when its secret is unset.

    No cross-kind fallback on purpose — see the module docstring."""
    env_name = _CHANNEL_BY_KIND.get(coop_kind)
    if not env_name:
        return None
    return os.environ.get(env_name) or None


def missing_channels() -> List[str]:
    """Every channel secret that is unset, for one loud startup log."""
    return [name for name in _CHANNEL_BY_KIND.values() if not os.environ.get(name)]
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd Project/Tests && python -m pytest test_coop_alert_router.py -v
```
Expected: PASS — 5 passed

- [ ] **Step 5: Log missing channels loudly at poll startup**

In `run_coop.py`'s `run()`, immediately after config load:

```python
    for name in missing_channels():
        logger.error(f"🔴 {name} is unset — alerts for that feed are DISABLED. "
                     f"Scraping and upserts continue.")
```

- [ ] **Step 6: Commit**

```
git add Project/Application/coop_alert_router.py Project/Tests/test_coop_alert_router.py Project/run_coop.py
git commit -m "feat(coop): per-feed Telegram routing with loud missing-secret logs"
```

---

### Task 4: Workflow cadence and secret wiring

Owner instruction: faster than 5 minutes, 06:00–17:00 Vienna. GitHub cron is UTC
and Vienna is UTC+2 in summer, so the window is `4-15` UTC.

**Files:**
- Modify: `.github/workflows/coop-fast-poll.yml`

- [ ] **Step 1: Change the cadence**

Replace the cron line and interval:

```yaml
    - cron: "*/15 4-15 * * 1-6"   # 06:00–17:00 Vienna (UTC+2 summer), Mon–Sat
```

```yaml
      POLL_INTERVAL_SECONDS: 120
```

Add a comment recording the winter-drift caveat directly above the cron:

```yaml
    # UTC. Vienna is UTC+2 in summer, so 4-15 is 06:00–17:00 local. In winter
    # (UTC+1) this window drifts one hour earlier, to 05:00–16:00 local.
```

- [ ] **Step 2: Wire the new secret**

Add to the job's `env:` block:

```yaml
          TELEGRAM_PRIVATE_COOP_CHANNEL_ID: ${{ secrets.TELEGRAM_PRIVATE_COOP_CHANNEL_ID }}
```

- [ ] **Step 3: Verify the workflow parses**

```
cd ~/Desktop/Startup/immo-scouter && python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/coop-fast-poll.yml')); print('YAML OK')"
```
Expected: `YAML OK`

- [ ] **Step 4: Verify the poll-window script still passes its tests**

```
cd Project/Tests && python -m pytest test_coop_poll_window.py -v
```
Expected: PASS. If the interval is asserted there, update the expected value to 120.

- [ ] **Step 5: Commit**

```
git add .github/workflows/coop-fast-poll.yml
git commit -m "chore(ci): 2-minute co-op poll, 06:00-17:00 Vienna"
```

---

### Task 5: Coverage measurement (`test_scope: true`)

- [ ] **Step 1: Record coverage before and after**

```
cd Project/Tests && python -m pytest --cov=Application.scraping.genossenschaft_scraper --cov=run_coop --cov=Application.coop_alert_router --cov-report=term-missing
```
Expected: coverage for the three touched modules is **not lower** than before this
plan. `coop_alert_router.py` should be at 100% — it is 20 lines with 5 tests.

- [ ] **Step 2: Run the full Python suite**

```
cd Project/Tests && python run_tests.py
```
Expected: 0 failures.

- [ ] **Step 3: Commit any coverage config changes**

```
git add -A && git commit -m "test: coverage baseline for co-op feed fixes" || echo "nothing to commit"
```

---

### Task 6: Visual verification (`ui_scope: true`)

Photos now reach `/coop`, so the DOM changes. Per `.claude/rules/ui-testing.md`
this is verified against real elements, not screenshots.

**Files:**
- Test: `dashboard/tests/coop.spec.ts`

- [ ] **Step 1: Start the dev server once**

```
cd dashboard && npm run dev &
```
Wait for `localhost:3000`.

- [ ] **Step 2: Write the DOM assertion**

Add to `dashboard/tests/coop.spec.ts`:

```typescript
test('coop rows render real photos once builder images resolve', async ({ page }) => {
  await page.goto('/coop');
  const rows = page.getByTestId('coop-row');
  await expect(rows.first()).toBeVisible();

  const thumbs = page.getByTestId('coop-thumb');
  const fallbacks = page.getByTestId('coop-thumb-fallback');
  const [nThumbs, nFallbacks] = [await thumbs.count(), await fallbacks.count()];

  // Every row gets exactly one of the two — no row is left with neither.
  expect(nThumbs + nFallbacks).toBe(await rows.count());

  // Each rendered photo points at an absolute builder/CDN URL, never a relative
  // path that would 404 against the dashboard's own origin.
  for (let i = 0; i < nThumbs; i++) {
    expect(await thumbs.nth(i).getAttribute('src')).toMatch(/^https?:\/\//);
  }
});
```

If `coop-row` is not an existing test id, add it to the row element in
`dashboard/app/coop/page.tsx` — the assertion needs a stable handle.

- [ ] **Step 3: Run only this spec**

```
cd dashboard && npx playwright test coop.spec.ts --reporter=dot
```
Expected: PASS

- [ ] **Step 4: Full suite as the final gate**

```
cd dashboard && npx playwright test --reporter=line
```
Expected: 0 failures on `/`, `/dashboard`, `/dashboard/map`, `/coop`.

**Known baseline:** main carries ~28 pre-existing `/dashboard/map` failures. Do
not attribute them to this change; compare against a baseline run on `main`
before concluding anything regressed.

- [ ] **Step 5: Stop the dev server**

```
pkill -f "next dev"
```

- [ ] **Step 6: Commit**

```
git add dashboard/tests/coop.spec.ts dashboard/app/coop/page.tsx
git commit -m "test(coop): assert every row renders a photo or a fallback"
```

---

## Owner-blocked step (cannot be automated)

Nothing in Task 3 or Task 4 delivers a notification until these exist:

1. Create two Telegram channels.
2. Add the bot as an administrator of each.
3. Add both repo secrets under Settings → Secrets and variables → Actions:
   - `TELEGRAM_COOP_CHANNEL_ID`
   - `TELEGRAM_PRIVATE_COOP_CHANNEL_ID`

Until then the new startup log prints `🔴 ... DISABLED` once per run, which is the
intended visible state rather than the previous silence.

## Verification that the fix actually worked

Photos resolve lazily at 40 units/poll, so `/coop` will not fill up instantly.
After roughly four delivered runs:

```
curl -s https://immo-agent-vienna.vercel.app/coop | grep -c 'data-testid="coop-thumb"'
```
Expected: greater than 0. It is currently 0.
