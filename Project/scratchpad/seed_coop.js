// Seed local immo.listings for the /coop Playwright spec. Deterministic.
// The /coop page is RENTALS-ONLY: it shows co-op units the poller has positively
// confirmed as rentals (buyable:false). Everything else must be excluded:
//   - buy-option units (buyable:true)
//   - legacy rows scraped before the buyable flag existed (field absent)
//   - Willhaben-sourced co-ops (coop_source:'willhaben')
//   - normal purchase listings (is_genossenschaft:false)
const now = Math.floor(Date.now() / 1000);
db = db.getSiblingDB('immo');
db.listings.deleteMany({});
db.listings.insertMany([
  {
    // VISIBLE #2 (older). Rental, no builder_url -> link falls back to the mygewo offer page.
    url: 'https://mygewo.at/genossenschaftswohnungen/angebot/genossenschaftswohnung-wien-3-zimmer-70-09-m2-oesw-e34fe1a4-5ecc-48cd-8378-a4958f5b7be8',
    title: 'Erzherzog-Karl-Straße 140, 1220 Wien – 3 Zimmer · 70 m² · OESW',
    address: 'Erzherzog-Karl-Straße 140, 1220 Wien',
    bezirk: '1220', rooms: 3, area_m2: 70.09, price_total: 945, own_funds: 2922,
    bautraeger: 'OESW', special_features: [], is_genossenschaft: true, buyable: false,
    source_enum: 'genossenschaft', coop_source: 'bautraeger_direct',
    url_is_valid: true, processed_at: now - 3 * 86400,
  },
  {
    // VISIBLE #1 (newest). Rental with builder_url -> links to the builder's page.
    url: 'https://mygewo.at/genossenschaftswohnungen/angebot/genossenschaftswohnung-wien-3-zimmer-63-m2-oevw-85a5472f-3ed9-42f4-8b4f-633571cec0d9',
    title: 'Thomas-Morus-Gasse 2-12, 1130 Wien – 3 Zimmer · 63 m² · OEVW',
    address: 'Thomas-Morus-Gasse 2-12, 1130 Wien',
    bezirk: '1130', rooms: 3, area_m2: 63, price_total: 550, own_funds: 2702,
    bautraeger: 'OEVW', special_features: [], is_genossenschaft: true, buyable: false,
    source_enum: 'genossenschaft', coop_source: 'bautraeger_direct',
    builder_url: 'https://www.oevw.at/suche/6127-leopoldauer-strasse-157a-2-23',
    url_is_valid: true, processed_at: now - 3600,
  },
  {
    // EXCLUDED: buy-option unit (buyable:true) — the exact thing the user rejects.
    url: 'https://mygewo.at/genossenschaftswohnungen/angebot/BUYOPTION-neues-leben-1100-eo',
    title: 'BUYOPTION-CONTROL Columbusgasse 1100 Wien', address: '1100 Wien',
    bezirk: '1100', rooms: 2, area_m2: 50, price_total: 778, is_genossenschaft: true,
    buyable: true, source_enum: 'genossenschaft', coop_source: 'bautraeger_direct',
    builder_url: 'https://www.wohnen.at/immobilienangebot/1100-wien-miete-mit-eo',
    url_is_valid: true, processed_at: now,
  },
  {
    // EXCLUDED: legacy row scraped before the buyable flag (field absent).
    url: 'https://mygewo.at/genossenschaftswohnungen/angebot/LEGACY-no-buyable-1210',
    title: 'LEGACY-CONTROL 1210 Wien', address: '1210 Wien', bezirk: '1210',
    rooms: 2, area_m2: 55, price_total: 600, is_genossenschaft: true,
    source_enum: 'genossenschaft', coop_source: 'bautraeger_direct',
    url_is_valid: true, processed_at: now,
  },
  {
    // EXCLUDED: normal purchase listing (not tagged co-op).
    url: 'https://www.willhaben.at/iad/x-not-coop',
    title: 'Eigentumswohnung 1010 Wien', address: '1010 Wien', bezirk: '1010',
    rooms: 2, area_m2: 60, price_total: 450000, is_genossenschaft: false,
    source_enum: 'willhaben', url_is_valid: true, processed_at: now,
  },
  {
    // EXCLUDED: mis-tagged Willhaben "co-op" (coop_source:'willhaben').
    url: 'https://www.willhaben.at/iad/x-willhaben-coop-eigentum',
    title: 'WILLHABEN-COOP-CONTROL Eigentum 1020 Wien', address: '1020 Wien',
    bezirk: '1020', rooms: 3, area_m2: 75, price_total: 389000,
    is_genossenschaft: true, buyable: false, source_enum: 'willhaben', coop_source: 'willhaben',
    url_is_valid: true, processed_at: now,
  },
]);
print('coop listings: ' + db.listings.countDocuments({ is_genossenschaft: true }));
print('total listings: ' + db.listings.countDocuments({}));
