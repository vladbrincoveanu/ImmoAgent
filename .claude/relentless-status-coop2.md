# Relentless status — coop mygewo filters (2)

## Task
Fix: (1) our crawler misses co-op units mygewo shows; (2) feed contains market-rate ("normal") rents, not genossenschaft-only.

## Branch
relentless/coop-mygewo-filters

## Diagnosis (VERIFIED live)
- Live mygewo RPC returns 61 Wien units (48 rental, 13 buyable). Both units in user's screenshot ARE in our RPC.
- COVERAGE BUG: valid cheap co-op units get hidden because their BUILDER deep-link 404s.
  Erzherzog-Karl ÖSW €945/70m² (cap 2921) → oesw.at deep-link = 404 → validate_url False
  → mark_url_invalid → url_is_valid=false → dropped from /coop. mygewo still shows it (links via own /angebot/).
- CLICK BUG: Thomas-Morus ÖVW → builder deep-link REDIRECTS to generic oevw.at/suche (HTTP 200) →
  user lands on a page of random/normal rentals. Explains "finding normal rents".
- FIX (unambiguous): build canonical mygewo /angebot/ URL for EVERY unit from its own fields.
  Format: genossenschaftswohnung-wien-{int rooms}-zimmer-{area '.'->'-'}-m2-{company.public_slug}-{uuid}
  VERIFIED: constructed URL returns 200 for deep-page units too.
- MARKET-RATE LEAK: mygewo mixes freifinanzierte rentals; no field flags it.
  €/m² not clean (showcased €945 unit = 13.5/m²). Legal hallmark = required Eigenmittel (capital). Needs user policy → ASKING.

## Progress
- [x] Reproduce both bugs against live RPC + production
- [x] Root-cause coverage bug (builder-URL 404 / redirect)
- [x] Verify mygewo /angebot/ canonical URL construction (200 for deep units)
- [ ] DECISION: genossenschaft-only filter policy (asking user)
- [ ] Implement canonical-URL fix in genossenschaft_scraper.py
- [ ] Implement co-op-only filter per decision
- [ ] Tests + verify

## Next action
Await filter-policy answer, then implement both fixes.
