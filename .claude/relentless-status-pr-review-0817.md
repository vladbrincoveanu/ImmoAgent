# Relentless Status

**Task:** Continue data-platform work and review the branch before PR
**Branch:** relentless/update-graphify-review
**Current step:** Grill complete; five review candidates confirmed with graph-backed evidence

## Progress
- [x] Inspect branch, worktree, and PR metadata
- [x] Analyze correctness, security, blast radius, and test gaps
- [x] Run focused verification and retain the prior project-level baseline
- [ ] Fix verified blocking issues without disturbing unrelated work
- [x] Re-review final diff and report findings

## Scope
- Review target: `origin/main...HEAD`
- Excluded: pre-existing uncommitted changes and generated graphify artifacts
- No GitHub PR currently exists for this branch

## Review candidates
- Normal production writers bypass `upsert_listing_with_history()` and canonical selection.
- Relists retain `url_is_valid=False` and stale `taken_at`.
- Coordinate precision/distance enrichment is not persisted in the committed branch.
- Active mygewo co-op records do not receive `seller_type`.
- District aggregation is not wired to a scheduler/CLI and uses direct Mongo handles.

## Next action
Address the blocking findings before opening or merging a PR. Do not count the current dirty worktree coordinate edits as part of the review target.

## Mission Checkpoint
- [x] Switched to an isolated relentless branch without changing existing worktree edits
- [x] Refreshed the code graph incrementally without an LLM: 6,094 nodes, 7,908 edges, 819 communities
- [x] Verified graph integrity: 0 missing, dangling, self-loop, duplicate, or collapsed edges
- [x] Compared graph delta: 5,396 -> 6,094 nodes and 6,632 -> 7,908 edges
- [x] Traced each review candidate through graphify-backed source evidence
- [x] Grilled each candidate and recorded a recommended resolution or explicit residual risk

## Graph Refresh
- Command: `graphify update .`
- Result: code graph rebuilt without an LLM; 6,094 nodes, 7,908 edges, 819 communities
- Visualization: skipped automatically because the graph exceeds the 5,000-node HTML limit
- Semantic caveat: the attempted document/image update found 156 changed non-code files but no configured LLM key; code graph refresh completed, semantic extraction for those files did not
- Token benchmark: 304,700 corpus words; approximately 6,859 tokens per average graph query; 59.2x reduction versus naive corpus reading
- Integrity: `graphify diagnose multigraph` reported 0 missing endpoints, 0 dangling endpoints, 0 self-loops, 0 duplicate edges, and 0 same-endpoint collapses
- Graph-backed traces: production writers, relist state, coordinate enrichment, mygewo mapping, and district aggregation were queried before targeted source reads

## Grill-Me Findings

### 1. High - Production Writers Bypass History And Canonical Selection
- Evidence: `Project/Application/main.py:442-557` opens a raw `pymongo` collection, uses `replace_one()` at lines 500-502, and is invoked at `Project/Application/main.py:837` after `Project/run.py` launches `Application.main`; the graph path for the intended static handler is separate: `save_listings_to_mongodb() -> .save_listings_to_mongodb() -> .upsert_listing_with_history()`.
- Evidence: normal scraper methods still call `.insert_listing()` directly at `Project/Application/scraping/willhaben_scraper.py:1926`, `immo_kurier_scraper.py:1249`, and `derstandard_scraper.py:1857`.
- Evidence: `pick_canonical_doc()` exists at `Project/Integration/mongodb_handler.py:64` but has no production callers; only its tests reference it.
- Grill question: Is this only a legacy path, or can scheduled production execution reach it?
- Recommended answer: It is production. `.github/workflows/scrapeJob.yml:33-35` runs `python Project/run.py`, which executes `Application.main`; the local writer is therefore the scheduled path.
- Grill question: What is the blast radius beyond missing canonical selection?
- Recommended answer: `replace_one()` replaces the full document from a fresh `Listing` and can erase price history, relist/taken state, send-state, and other fields not present in the new scrape. Direct `insert_listing()` also skips history and canonical selection.
- Grill question: What is the smallest acceptable resolution?
- Recommended answer: Make every production writer delegate to one handler-owned write API that performs validation, unit/content fingerprinting, price history, relist transitions, and canonical selection. Remove raw collection writes from application/scraper paths rather than adding another parallel writer.
- Fix gate: Add an integration test for each production entry point asserting the handler history/canonical API is called and raw `replace_one()`/`insert_one()` is not used for normal listing writes; assert persisted historical fields survive a normal re-scrape.

### 2. High - Relists Retain Invalid URL State And Stale Taken Timestamp
- Evidence: `MongoDBHandler.mark_listing_taken()` at `Project/Integration/mongodb_handler.py:466-477` sets `listing_status="taken"`, `taken_at`, and `url_is_valid=False`.
- Evidence: `upsert_listing_with_history()` at lines 410-428 sets a relisted document back to `listing_status="active"`, but does not set `url_is_valid=True` or unset `taken_at`.
- Evidence: `_replace_preserving_state()` at lines 245-261 explicitly carries `url_is_valid` forward, so the co-op upsert path preserves the invalid flag on reappearance as well.
- Grill question: Is retaining `taken_at` intentional historical data or stale current-state data?
- Recommended answer: It is stale current-state data. The historical value is already represented by `relist_events[].delisted_at`; the active cycle must not continue to expose `taken_at`.
- Grill question: Can the upsert safely set `url_is_valid=True` without performing a URL check?
- Recommended answer: Only when the caller has passed the mandatory URL validation gate. Either validate before the state transition or pass an explicit validated result; do not silently claim URL validity from a database upsert alone.
- Grill question: What is the smallest acceptable resolution?
- Recommended answer: On a validated relist, atomically set `listing_status="active"` and `url_is_valid=True`, and `$unset` the current-cycle `taken_at`; retain the old timestamp in the relist event. Apply the same invariant to co-op replacement.
- Fix gate: Extend `Tests/test_relist_events.py` with an existing taken document containing `url_is_valid=False` and `taken_at`; assert the update sets the active/valid state and unsets the current `taken_at`. Add a co-op replacement regression test.

### 3. High - Coordinate Precision And Distance Enrichment Are Not Persisted In The Review Target
- Evidence: commit `48def99` adds precision and walk-distance calculations in `Project/Application/main.py`, but the committed call to `update_listing_coordinates()` occurs before those fields are added to the update payload; the committed `update_listing_coordinates()` only writes coordinates, source, and landmark hint.
- Evidence: the duplicate path only enters enrichment when `not existing_by_fingerprint.get('coordinates')`, so an existing coarse landmark coordinate cannot be upgraded to an exact coordinate.
- Evidence: `prior_precision` is computed from the newly scraped `listing_dict`, not from the existing Mongo document, so it does not reliably compare against the persisted precision tier.
- Evidence: the current dirty worktree moves the update call and extends the handler payload, but those edits are outside `origin/main...HEAD` and are not a complete fix for the coarse-coordinate guard or existing-document comparison.
- Grill question: Does the current precision test prove the production bug is fixed?
- Recommended answer: No. `Tests/test_coordinate_precision.py` tests the helper and the handler payload in isolation; it does not exercise `Application.main.save_listings_to_mongodb()` with an existing coarse-coordinate document.
- Grill question: What is the intended upgrade rule?
- Recommended answer: Persist a new geocode only when its precision is better than the persisted document's precision, while never downgrading an exact fix. Compare against `existing_by_fingerprint` or a normalized persisted precision field.
- Grill question: What is the smallest acceptable resolution?
- Recommended answer: Build one enrichment payload, calculate precision and walk distances before the handler update, change the guard to a precision comparison, and persist all fields through the handler. Keep backfill callers compatible by omitting optional fields when absent.
- Fix gate: Add a writer-level test covering no coordinates -> exact and landmark -> exact upgrades, asserting `$set` contains coordinates, `coordinate_precision_m`, `school_walk_minutes`, and `ubahn_walk_minutes`; add a no-downgrade test for exact -> landmark.

### 4. Medium/High - Active MyGEWO Records Omit seller_type
- Evidence: graph trace `_units_to_listings() -> _new_coop_listing()` reaches `Project/Application/scraping/genossenschaft_scraper.py:429-491`; `_new_coop_listing()` sets the co-op identity but not `seller_type`, and the mygewo mapper has no later assignment.
- Evidence: the mapper deliberately skips text field extractors because the RPC payload is structured and has no free-text field. `extract_seller_type()` would nevertheless return `bautraeger` when `is_genossenschaft=True` and no agency/private marker exists.
- Evidence: the direct pilot parsers assign `seller_type` at lines 158, 189, and 219, while mygewo is the active production source in `SOURCES` at lines 56-64.
- Grill question: Is `seller_type` required for mygewo or only for text-rich scraped ads?
- Recommended answer: It is required for schema consistency. MyGEWO is explicitly a builder-direct co-op feed, so its default should be `bautraeger`, with any future explicit agency marker taking precedence.
- Grill question: Could the omission be harmless because the dashboard can infer `is_genossenschaft`?
- Recommended answer: No. Consumers and filters use `seller_type` as a separate field; leaving it null creates inconsistent active records and wholesale co-op replacement can erase a previously populated value.
- Grill question: What is the smallest acceptable resolution?
- Recommended answer: Assign `listing.seller_type = extract_seller_type('', is_genossenschaft=True)` or an explicit `bautraeger` value in the mygewo mapping, then preserve it through upsert. Add a migration/backfill only if existing records must be corrected before the next poll.
- Fix gate: Add a parser assertion that every emitted mygewo rental has `seller_type == "bautraeger"`; add an upsert assertion that re-polling does not erase seller_type.

### 5. Medium/High - District Aggregation Is Dead Code And Violates The Mongo Access Boundary
- Evidence: `Project/Application/analytics/district_snapshot.py:75-102` defines `run_monthly_aggregation()` but graph queries found no production caller; the only caller is `Tests/test_district_snapshot.py:37`.
- Evidence: no workflow or CLI references `run_monthly_aggregation`, `district_snapshot`, or `district_snapshots`; existing cron workflows schedule scraping, top-five, outreach, cleanup, and co-op polling instead.
- Evidence: the function directly calls `mongo_handler.collection.find()` and `mongo_handler.db["district_snapshots"].update_one()`, violating the project rule that MongoDB access goes through `mongodb_handler.py` methods only.
- Grill question: Is an uncalled analytics helper a blocking defect or merely unfinished scope?
- Recommended answer: It is blocking if the PR claims monthly district snapshots; otherwise remove it from this PR or explicitly mark it as deferred. Shipping tests for an unreachable feature creates false completeness.
- Grill question: What is the smallest acceptable resolution if the feature ships now?
- Recommended answer: Add handler-owned methods for the period query and snapshot upsert, add a CLI/job entry point, and schedule it with a monthly workflow; keep `district_snapshot.py` pure over supplied records and call only handler methods.
- Grill question: What proves the wiring is real?
- Recommended answer: A CLI smoke test invokes the job with a fake handler, a workflow test or static check verifies the scheduled command, and a handler contract test proves no analytics module accesses `.collection` or `.db` directly.
- Fix gate: Do not merge as complete until there is one production caller, one scheduler/CLI path, and persistence tests through `MongoDBHandler` methods rather than raw collection mocks.

## Residual Risks And Review Boundary
- The current worktree remains dirty with unrelated user/generated changes; none were reverted.
- The graph refresh is code-complete but semantic extraction for changed documents/images was skipped because no LLM key is configured; conclusions above rely on code graph traversal plus targeted source reads.
- Focused review tests: 37 passed after correcting the repository's `Tests/` path case.
- Full suite was not rerun in this mission; the prior recorded baseline is not green, with the first failure reported as a pre-existing root `main.py` test-signature mismatch.
- No implementation fixes were made in this mission; all five candidates remain open until their fix gates pass.

## Verification
- Focused review set: 37 passed after correcting the repository's case-sensitive `Tests/` path
- Prior status record: focused data-platform tests 25 passed; related persistence/geocoding tests 8 passed
- Full suite: not rerun in this mission; prior first failure is a pre-existing root `main.py` test-signature mismatch
- `git diff --check origin/main...HEAD`: clean
