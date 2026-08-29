# All MyGEWO Co-op Alerts

## Problem

The `/alerts` page currently creates `coop_private` alerts by default. That
kind intentionally requires a Willhaben listing classified as a private tenant
handover (`coop_kind == "private_transfer"`). Builder-direct MyGEWO rentals
are a separate feed: they carry `coop_source == "bautraeger_direct"` and do
not carry the private-handover verdict. As a result, a user who wants all new
co-op rentals sees successful Telegram test messages but no MyGEWO listing
deliveries.

The existing `keyword` kind cannot solve this by itself. MyGEWO titles contain
address, rooms, area, and builder data, not necessarily the German co-op marker
words prefilled by the form. An empty keyword list would also widen the user
alert to the whole mixed new-rentals feed, including ordinary Willhaben ads.

## Design

Add a distinct `mygewo` alert kind for builder-direct co-op rentals.

- `mygewo` matches only listings with `coop_source == "bautraeger_direct"`.
- Numeric filters continue to apply through the shared matcher.
- Keywords remain optional additional narrowing filters. The all-MyGEWO form
  default sends no keyword filter.
- `coop_private` keeps its existing private-handover rubric and keyword
  behavior.
- Legacy missing/null-kind records remain private broad-feed subscriptions via
  the existing `None` sentinel.
- `mygewo` is added to private user-alert query/validation paths only.
- `CHANNEL_ALERT_KINDS` remains `['coop_private', 'keyword']`; personal
  `mygewo` alerts cannot change broadcast channel filtering.

The dashboard feed control will make the two choices explicit: all
builder-direct MyGEWO rentals or private tenant handovers. New all-MyGEWO
alerts use `mygewo` and start with an empty keyword field. Existing
`coop_private` documents are not migrated or reinterpreted; users who want the
new scope delete and recreate the alert.

## Data Flow

1. The dashboard submits `kind: "mygewo"` with optional numeric filters and
   optional keywords.
2. The API accepts and stores the kind using the existing subscription schema.
3. `run_coop.py` requests `mygewo` alongside private user-alert kinds, without
   adding it to the broadcast filter query.
4. `alert_matcher.rubric_hit()` scopes `mygewo` matches to
   `coop_source == "bautraeger_direct"`.
5. Existing `match()` and `dispatch()` deliver through Telegram and/or
   confirmed email, with the existing delivery ledger and retry behavior.

## Error Handling

- Unknown kinds remain rejected by the dashboard API.
- Missing `coop_source` fails a `mygewo` rubric match rather than widening the
  alert to an unclassified listing.
- Existing alert delivery failures remain non-fatal to scraping and upserts.
- No database migration or automatic rewrite of existing subscriptions is
  performed.

## Testing

- Matcher test: a builder-direct listing matches `mygewo` with no keywords.
- Matcher test: a Willhaben listing and an unclassified listing do not match
  `mygewo`.
- Delivery test: a new MyGEWO candidate reaches a Telegram user alert with
  `kind: "mygewo"`.
- Isolation test: `mygewo` is requested for private delivery but remains absent
  from `CHANNEL_ALERT_KINDS`.
- API test: `mygewo` is accepted and unknown kinds remain rejected.
- Preserve the legacy missing-kind regression and private-handover tests.
- Run the complete Python suite, dashboard test suite, and dashboard build.

## Non-Goals

- Changing private tenant-handover matching.
- Broadening `keyword` or legacy alerts.
- Changing broadcast channel routing or channel credentials.
- Adding alert editing or automatic subscription migration.
- Deploying or pushing changes without explicit authorization.
