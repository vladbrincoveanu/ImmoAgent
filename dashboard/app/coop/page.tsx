import { getDb } from '@/lib/mongodb';
import { Document } from 'mongodb';

// Always render fresh — new co-op units land every few minutes via the poller.
export const dynamic = 'force-dynamic';

export const metadata = {
  title: 'Genossenschaftswohnungen — Live',
};

// Parking spots / storage units occasionally slip through a builder's own site
// tagged as "Wohnung" (e.g. a 12,5 m² Stellplatz) — below this, it isn't housing.
const MIN_LIVABLE_AREA_M2 = 15;

type CoopRow = {
  url: string;
  title: string | null;
  address: string | null;
  bezirk: string | null;
  rooms: number | null;
  area_m2: number | null;
  price_total: number | null;
  own_funds: number | null;
  bautraeger: string | null;
  builder_url: string | null;
  special_features: string[];
  processed_at: number | null;
};

const ROW_LIMIT = 200;

// Co-op RENTALS have a low €/m² and no purchase price, so the purchase-tuned
// map filters don't apply here — just show valid co-op units, newest first.
// Builder-direct only: Willhaben-sourced rows are excluded because they link
// to Willhaben (not the builder's reservation page) and can leak mis-tagged
// for-sale (Eigentum) units onto this rentals-only page.
// buyable:false is a POSITIVE rental confirmation the poller stamps on every
// unit it emits (buy-option units are dropped at scrape). Requiring it (not
// just $ne:true) also hides legacy rows scraped before this flag existed —
// they reappear within one poll cycle once re-scraped as rentals.
// bezirk + area_m2 are a defense-in-depth guard, independent of the flags
// above: the (now-disabled) standalone ÖVW/Familienwohnbau/BWSG adapters had
// no Vienna scoping and no housing-size floor, so a stray non-Wien or
// garage/storage row must never render here regardless of DB state.
const BASE_QUERY: Document = {
  is_genossenschaft: true,
  url_is_valid: { $ne: false },
  coop_source: { $ne: 'willhaben' },
  buyable: false,
  bezirk: { $regex: '^1\\d{3}$' },
  // { area_m2: null } already matches missing/undefined fields in MongoDB —
  // no separate $exists:false clause needed.
  $or: [{ area_m2: null }, { area_m2: { $gte: MIN_LIVABLE_AREA_M2 } }],
};

type Filters = {
  bezirk: string;
  bautraeger: string;
  rooms: string[];
  area: string[];
  rent: string[];
  capital: string[];
  feature: string[];
};

/** Filters run in MongoDB, NOT in JS over the fetched page: filtering client-side
 * would only ever search the newest ROW_LIMIT rows, so a match older than that
 * would silently not exist. */
function buildQuery(f: Filters): Document {
  // Every group is its own $and entry: a bare $or key would collide with
  // BASE_QUERY's area-floor $or and with the other groups' $or clauses.
  const and: Document[] = [BASE_QUERY];
  if (f.bezirk) and.push({ bezirk: f.bezirk });
  if (f.bautraeger) and.push({ bautraeger: f.bautraeger });
  for (const [field, buckets, selected] of [
    ['rooms', ROOM_BUCKETS, f.rooms],
    ['area_m2', AREA_BUCKETS, f.area],
    ['price_total', RENT_BUCKETS, f.rent],
    ['own_funds', CAPITAL_BUCKETS, f.capital],
  ] as [string, Bucket[], string[]][]) {
    const clauses = bucketClauses(field, buckets, selected);
    // An unknown bucket value must not silently widen the result set — an
    // active-but-unmatchable filter yields nothing rather than everything.
    if (selected.length) and.push(clauses.length ? { $or: clauses } : { _id: null });
  }
  // OR-within-category, same as every other filter here — confirmed live on
  // mygewo.at: checking a 2nd Freifläche WIDENS the result count, it doesn't
  // narrow it (their checkboxes are "any of", not "all of").
  if (f.feature.length) and.push({ special_features: { $in: f.feature } });
  return { $and: and };
}

async function getCoopListings(
  filters: Filters,
): Promise<{
  rows: CoopRow[];
  districts: string[];
  builders: string[];
  total: number;
  dbUp: boolean;
}> {
  const db = getDb();
  if (!db) return { rows: [], districts: [], builders: [], total: 0, dbUp: false };
  try {
    const coll = db.collection<Document>('listings');
    const query = buildQuery(filters);
    // Dropdown options come from the FULL unfiltered set, not the current page —
    // otherwise picking a district could remove it from its own dropdown.
    const [docs, total, allDistricts, allBuilders] = await Promise.all([
      coll.find(query).sort({ processed_at: -1, _id: -1 }).limit(ROW_LIMIT).toArray(),
      coll.countDocuments(query),
      coll.distinct('bezirk', BASE_QUERY),
      coll.distinct('bautraeger', BASE_QUERY),
    ]);
    const strings = (v: unknown[]) =>
      v.filter((d): d is string => typeof d === 'string' && d.length > 0).sort();
    const districts = strings(allDistricts as unknown[]);
    const builders = strings(allBuilders as unknown[]);
    const rows = docs.map((d): CoopRow => {
      return {
        url: String(d.url ?? ''),
        title: (d.title as string) ?? null,
        address: (d.address as string) ?? null,
        bezirk: (d.bezirk as string) ?? null,
        rooms: typeof d.rooms === 'number' ? d.rooms : null,
        area_m2: typeof d.area_m2 === 'number' ? d.area_m2 : null,
        price_total: typeof d.price_total === 'number' ? d.price_total : null,
        own_funds: typeof d.own_funds === 'number' ? d.own_funds : null,
        bautraeger: (d.bautraeger as string) ?? null,
        builder_url: (d.builder_url as string) ?? null,
        special_features: Array.isArray(d.special_features) ? (d.special_features as string[]) : [],
        processed_at: typeof d.processed_at === 'number' ? d.processed_at : null,
      };
    });
    return { rows, districts, builders, total, dbUp: true };
  } catch {
    return { rows: [], districts: [], builders: [], total: 0, dbUp: false };
  }
}

function fmtInt(n: number | null): string {
  return n == null ? '—' : new Intl.NumberFormat('de-AT').format(Math.round(n));
}

function fmtArea(n: number | null): string {
  return n == null ? '—' : `${new Intl.NumberFormat('de-AT', { maximumFractionDigits: 1 }).format(n)} m²`;
}

function ago(ts: number | null): string | null {
  if (!ts) return null;
  const secs = Math.floor(Date.now() / 1000) - ts;
  if (secs < 0) return null;
  const d = Math.floor(secs / 86400);
  if (d >= 1) return `vor ${d} ${d === 1 ? 'Tag' : 'Tagen'}`;
  const h = Math.floor(secs / 3600);
  if (h >= 1) return `vor ${h} h`;
  const m = Math.max(1, Math.floor(secs / 60));
  return `vor ${m} min`;
}

// Bucket definitions mirror mygewo.at/genossenschaftswohnungen/suche's own
// filter panel (Zimmer / Fläche / Miete / Kapital / Freiflächen) so /coop reads
// as the same filter vocabulary a mygewo user already knows.
type Bucket = { value: string; label: string; min?: number; max?: number };

/** Bucket → a Mongo range on `field`. Bounds are inclusive on both ends where
 * the mygewo labels overlap (€500–749 next to "bis €500"), matching the JS
 * predicates this replaced. */
function bucketClauses(field: string, buckets: Bucket[], selected: string[]): Document[] {
  return selected.flatMap((v) => {
    const b = buckets.find((x) => x.value === v);
    if (!b) return [];
    const range: Document = {};
    if (b.min != null) range.$gte = b.min;
    if (b.max != null) range.$lte = b.max;
    return [{ [field]: range }];
  });
}

// Rooms are matched on the rounded value the UI shows, so 2.5 Zimmer lands in
// the "3" bucket exactly as `Math.round` did client-side.
const ROOM_BUCKETS: Bucket[] = [
  { value: '1', label: '1', min: 0.5, max: 1.49 },
  { value: '2', label: '2', min: 1.5, max: 2.49 },
  { value: '3', label: '3', min: 2.5, max: 3.49 },
  { value: '4', label: '4+', min: 3.5 },
];

// Bounds are contiguous (not >=51/>=75 as the mygewo labels might suggest) so a
// float area like 50.4 m² — routine given real scraped values (e.g. 70.09) —
// always falls in exactly one bucket instead of none.
const AREA_BUCKETS: Bucket[] = [
  { value: '0-50', label: 'bis 50 m²', max: 50 },
  { value: '51-74', label: '51–74 m²', min: 50.01, max: 74 },
  { value: '75-99', label: '75–99 m²', min: 74.01, max: 99 },
  { value: '100-', label: 'ab 100 m²', min: 99.01 },
];

const RENT_BUCKETS: Bucket[] = [
  { value: '0-500', label: 'bis €500', max: 500 },
  { value: '500-749', label: '€500–749', min: 500, max: 749 },
  { value: '750-999', label: '€750–999', min: 750, max: 999 },
  { value: '1000-', label: 'ab €1.000', min: 1000 },
];

const CAPITAL_BUCKETS: Bucket[] = [
  { value: '0-5000', label: 'bis €5.000', max: 5000 },
  { value: '5000-9999', label: '€5.000–9.999', min: 5000, max: 9999 },
  { value: '10000-19999', label: '€10.000–19.999', min: 10000, max: 19999 },
  { value: '20000-', label: 'ab €20.000', min: 20000 },
];

const FEATURE_OPTIONS = ['Garten', 'Loggia', 'Balkon', 'Terrasse'] as const;

function toArray(v: string | string[] | undefined): string[] {
  if (!v) return [];
  return Array.isArray(v) ? v : [v];
}

type Search = {
  bezirk?: string;
  bautraeger?: string;
  rooms?: string | string[];
  area?: string | string[];
  rent?: string | string[];
  capital?: string | string[];
  feature?: string | string[];
};

export default async function CoopPage({
  searchParams,
}: {
  searchParams: Promise<Search>;
}) {
  const sp = await searchParams;

  // Filter controls are pure GET params (SSR, no client JS); they're applied in
  // the DB query, so they search the whole inventory, not just the first page.
  const bezirk = typeof sp.bezirk === 'string' ? sp.bezirk : '';
  const bautraeger = typeof sp.bautraeger === 'string' ? sp.bautraeger : '';
  const rooms = toArray(sp.rooms);
  const area = toArray(sp.area);
  const rent = toArray(sp.rent);
  const capital = toArray(sp.capital);
  const feature = toArray(sp.feature);

  const { rows: filtered, districts, builders, total, dbUp } = await getCoopListings({
    bezirk,
    bautraeger,
    rooms,
    area,
    rent,
    capital,
    feature,
  });

  const inputCls =
    'rounded-lg border border-[#E8E4E0] bg-white px-3 py-1.5 text-sm text-[#2D2D2D]';
  const chipCls =
    'cursor-pointer select-none rounded-full border border-[#E8E4E0] bg-white px-3 py-1 text-xs font-medium text-[#2D2D2D] transition-colors has-[:checked]:border-[#3D405B] has-[:checked]:bg-[#3D405B] has-[:checked]:text-white';
  const groupLabelCls = 'mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-[#6B6B6B]';

  const chipGroup = (name: string, options: Bucket[], selected: string[], testidPrefix: string) => (
    <div className="flex flex-wrap gap-1.5">
      {options.map((opt) => (
        <label key={opt.value} className={chipCls} data-testid={`${testidPrefix}-${opt.value}`}>
          <input
            type="checkbox"
            name={name}
            value={opt.value}
            defaultChecked={selected.includes(opt.value)}
            className="sr-only"
          />
          {opt.label}
        </label>
      ))}
    </div>
  );

  return (
    <main className="mx-auto max-w-4xl px-4 py-8" data-testid="coop-page">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-[#3D405B]">Genossenschaftswohnungen</h1>
        <p className="mt-1 text-sm text-[#6B6B6B]">
          Live-Treffer, aggregiert von{' '}
          <a
            href="https://mygewo.at/genossenschaftswohnungen/suche"
            className="underline hover:text-[#3D405B]"
            target="_blank"
            rel="noopener noreferrer"
          >
            mygewo.at
          </a>{' '}
          über alle Bauträger · nur Miete (keine Kaufoption) · Wien ·
          Aktualisierung alle 5&nbsp;Min.
        </p>

        <form
          method="get"
          data-testid="coop-filters"
          className="mt-4 space-y-3 rounded-xl border border-[#E8E4E0] bg-white p-4"
        >
          <div className="flex flex-wrap gap-2">
            <select name="bezirk" defaultValue={bezirk} data-testid="filter-bezirk" className={inputCls}>
              <option value="">Alle Bezirke</option>
              {districts.map((d) => (
                <option key={d} value={d}>
                  {d}
                </option>
              ))}
            </select>
            <select
              name="bautraeger"
              defaultValue={bautraeger}
              data-testid="filter-bautraeger"
              className={inputCls}
            >
              <option value="">Alle Bauträger</option>
              {builders.map((b) => (
                <option key={b} value={b}>
                  {b}
                </option>
              ))}
            </select>
          </div>

          <div>
            <span className={groupLabelCls}>Zimmer</span>
            {chipGroup('rooms', ROOM_BUCKETS, rooms, 'filter-rooms')}
          </div>

          <div>
            <span className={groupLabelCls}>Fläche</span>
            {chipGroup('area', AREA_BUCKETS, area, 'filter-area')}
          </div>

          <div>
            <span className={groupLabelCls}>Miete</span>
            {chipGroup('rent', RENT_BUCKETS, rent, 'filter-rent')}
          </div>

          <div>
            <span className={groupLabelCls}>Kapital</span>
            {chipGroup('capital', CAPITAL_BUCKETS, capital, 'filter-capital')}
          </div>

          <div>
            <span className={groupLabelCls}>Freiflächen</span>
            <div className="flex flex-wrap gap-1.5">
              {FEATURE_OPTIONS.map((f) => (
                <label key={f} className={chipCls} data-testid={`filter-feature-${f}`}>
                  <input
                    type="checkbox"
                    name="feature"
                    value={f}
                    defaultChecked={feature.includes(f)}
                    className="sr-only"
                  />
                  {f}
                </label>
              ))}
            </div>
          </div>

          <div className="flex items-center gap-2 pt-1">
            <button
              type="submit"
              data-testid="filter-apply"
              className="rounded-lg bg-[#3D405B] px-3 py-1.5 text-sm font-medium text-white hover:opacity-90"
            >
              Filtern
            </button>
            <a href="/coop" data-testid="filter-reset" className="px-2 py-1.5 text-sm text-[#6B6B6B] underline">
              Zurücksetzen
            </a>
          </div>
        </form>

        <p className="mt-3 text-sm font-medium text-[#3D405B]" data-testid="coop-count">
          {total} Treffer
          {total > filtered.length && ` · zeigt die ${filtered.length} neuesten`}
        </p>
      </div>

      {!dbUp && (
        <div
          data-testid="coop-db-error"
          className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-800"
        >
          Datenbank nicht erreichbar — bitte später erneut versuchen.
        </div>
      )}

      {dbUp && filtered.length === 0 && (
        <div
          data-testid="coop-empty"
          className="rounded-lg border border-[#E8E4E0] bg-white px-4 py-8 text-center text-sm text-[#6B6B6B]"
        >
          Aktuell keine passenden Genossenschaftswohnungen. Sobald ein neues Angebot
          erscheint, taucht es hier (und im Telegram-Kanal) auf.
        </div>
      )}

      <ul className="space-y-3" data-testid="coop-list">
        {filtered.map((r) => {
          const posted = ago(r.processed_at);
          return (
            <li key={r.url} data-testid="coop-item">
              <a
                href={r.builder_url || r.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block rounded-lg border border-[#E8E4E0] bg-white px-4 py-3 transition-colors hover:bg-[#FBFAF8]"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="truncate font-semibold text-[#3D405B]" data-testid="coop-address">
                      {r.address || r.title || 'Genossenschaftswohnung'}
                    </div>
                    <div className="mt-1 text-sm text-[#2D2D2D]" data-testid="coop-specs">
                      <span data-testid="coop-rooms">{r.rooms != null ? `${Math.round(r.rooms)} Zimmer` : '—'}</span>
                      {' · '}
                      <span data-testid="coop-area">{fmtArea(r.area_m2)}</span>
                      {' · '}
                      <span className="font-medium" data-testid="coop-rent">
                        {r.price_total != null ? `€${fmtInt(r.price_total)} Miete` : 'Miete —'}
                      </span>
                      {r.own_funds != null && (
                        <>
                          {' · '}
                          <span data-testid="coop-capital">Kapital €{fmtInt(r.own_funds)}</span>
                        </>
                      )}
                    </div>
                    {r.special_features.length > 0 && (
                      <div className="mt-1 text-xs text-[#6B6B6B]" data-testid="coop-features">
                        {r.special_features.join(' · ')}
                      </div>
                    )}
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    {r.bezirk && (
                      <span
                        data-testid="coop-district"
                        className="rounded bg-[#3D405B] px-2 py-0.5 text-xs font-medium text-white"
                      >
                        {r.bezirk}
                      </span>
                    )}
                  </div>
                </div>
                <div className="mt-1 flex items-center gap-2 text-xs text-[#6B6B6B]">
                  {r.bautraeger && <span data-testid="coop-dev">{r.bautraeger}</span>}
                  {posted && <span>· {posted}</span>}
                  <span className="ml-auto text-[#3D405B]">Zum Angebot →</span>
                </div>
              </a>
            </li>
          );
        })}
      </ul>
    </main>
  );
}
