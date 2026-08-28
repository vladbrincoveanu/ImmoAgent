# Legacy Alert Kind Compatibility

## Problem

Older dashboard-created alert documents do not store `kind`. The dashboard
already treats a missing or null `kind` as the legacy `listings` feed, but the
poller's explicit kind query skips those documents. This silently disables
alerts for users who created them before `kind` was introduced.

## Design

Include `None` in the private user-alert kind list. MongoDB's existing
`{"kind": {"$in": kinds}}` query then matches both explicit `listings` records
and legacy records whose field is missing or null. The alert matcher already
treats a missing kind as the general feed, so no matcher change is needed.

Keep the broadcast channel kind list unchanged: only `coop_private` and
`keyword` can influence co-op channel filtering. Legacy user alerts remain
private subscriptions and cannot reopen the broadcast feed.

## Testing

Replace the current legacy regression fixture with the real old dashboard shape:
confirmed email-only subscription, search parameters, no `kind`, and no scalar
keyword. Assert that the private poll query requests the legacy sentinel and
that the email dispatcher delivers. Retain the channel-isolation regression to
assert that the broadcast query excludes the sentinel.

## Alternatives Rejected

- One-time database migration: adds a production write and migration failure
  mode for a compatibility issue the existing query can handle.
- New handler query flag: clearer but expands an API used by one poller without
  changing the required behavior.
