# Relentless Status (history-rewrite + map-overhaul)

**Task:** remove git history (API keys) + continue 2026-06-07-map-overhaul-design.md
**Started:** 2026-06-07T09:05:00+02:00
**Branch:** TBD (will create `relentless/map-overhaul-2026-06-07` after history rewrite)
**Current step:** 1 of 2 (history rewrite in progress, spec implementation queued)

## Phase 1: Git history rewrite
- Backup .git to /tmp/immo-scouter-git-backup-2026-06-07.tar.gz
- Use git-filter-repo --replace-text to replace sk-cp-... and fw_... with REDACTED in all blobs
- Verify with `git log --all -S <key>` (should return empty)
- Note: I will NOT force-push to origin. Local rewrite only. User must also ROTATE the keys at the provider regardless.

## Phase 2: Spec implementation (10 steps per §7 of design spec)
1. Add url_is_valid to MapListing + /api/listings/map projection
2. Fix empty state line (1-line)
3. Pin click stopPropagation
4. 1-click pin/sidebar → modal; delete SelectedCard
5. URL sync (detail/district/min_score/max_price)
6. New /api/listings/[id]/context endpoint
7. New Sparkline component
8. ListingDetail enrichment
9. SSE merge → banner pattern
10. Playwright tests

## End state
- 0 keys in `git log --all -S <key>` (history clean locally)
- All 10 spec steps implemented and committed
- `npx playwright test --reporter=list` passes
- `npx tsc --noEmit` clean
