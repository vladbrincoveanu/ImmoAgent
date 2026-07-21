// Seed the local immo.listings with the two live mygewo matches (+ one non-coop
// control that must NOT appear on /coop). Deterministic for Playwright.
const now = Math.floor(Date.now() / 1000);
db = db.getSiblingDB('immo');
db.listings.deleteMany({});
db.listings.insertMany([
  {
    url: 'https://mygewo.at/genossenschaftswohnungen/angebot/genossenschaftswohnung-wien-3-zimmer-70-09-m2-oesw-e34fe1a4-5ecc-48cd-8378-a4958f5b7be8',
    title: 'Erzherzog-Karl-Straße 140, 1220 Wien – 3 Zimmer · 70 m² · OESW',
    address: 'Erzherzog-Karl-Straße 140, 1220 Wien',
    bezirk: '1220', rooms: 3, area_m2: 70.09, price_total: 945, own_funds: 2922,
    bautraeger: 'OESW', special_features: [], is_genossenschaft: true,
    source_enum: 'genossenschaft', coop_source: 'bautraeger_direct',
    url_is_valid: true, processed_at: now - 3 * 86400,
  },
  {
    url: 'https://mygewo.at/genossenschaftswohnungen/angebot/genossenschaftswohnung-wien-3-zimmer-63-m2-oevw-85a5472f-3ed9-42f4-8b4f-633571cec0d9',
    title: 'Thomas-Morus-Gasse 2-12, 1130 Wien – 3 Zimmer · 63 m² · OEVW',
    address: 'Thomas-Morus-Gasse 2-12, 1130 Wien',
    bezirk: '1130', rooms: 3, area_m2: 63, price_total: 550, own_funds: 2702,
    bautraeger: 'OEVW', special_features: ['Kaufoption'], is_genossenschaft: true,
    source_enum: 'genossenschaft', coop_source: 'bautraeger_direct',
    // resolved builder reservation deep-link — /coop must link here, not to mygewo
    builder_url: 'https://www.oevw.at/suche/6127-leopoldauer-strasse-157a-2-23',
    url_is_valid: true, processed_at: now - 3600,
  },
  {
    // control 1: a normal purchase listing (not tagged co-op) — excluded by is_genossenschaft
    url: 'https://www.willhaben.at/iad/x-not-coop',
    title: 'Eigentumswohnung 1010 Wien', address: '1010 Wien', bezirk: '1010',
    rooms: 2, area_m2: 60, price_total: 450000, is_genossenschaft: false,
    source_enum: 'willhaben', url_is_valid: true, processed_at: now,
  },
  {
    // control 2: a mis-tagged Willhaben "co-op" (coop_source=willhaben) — the exact
    // bug case: for-sale flat that matched a co-op keyword. Must be excluded from
    // /coop (builder-direct only), and must NOT link to willhaben.
    url: 'https://www.willhaben.at/iad/x-willhaben-coop-eigentum',
    title: 'WILLHABEN-COOP-CONTROL Eigentum 1020 Wien', address: '1020 Wien',
    bezirk: '1020', rooms: 3, area_m2: 75, price_total: 389000,
    is_genossenschaft: true, source_enum: 'willhaben', coop_source: 'willhaben',
    url_is_valid: true, processed_at: now,
  },
]);
print('coop listings: ' + db.listings.countDocuments({ is_genossenschaft: true }));
print('total listings: ' + db.listings.countDocuments({}));
