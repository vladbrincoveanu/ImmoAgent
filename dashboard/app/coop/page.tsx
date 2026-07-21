import { getDb } from '@/lib/mongodb';
import { Document } from 'mongodb';

// Always render fresh — new co-op units land every few minutes via the poller.
export const dynamic = 'force-dynamic';

export const metadata = {
  title: 'Genossenschaftswohnungen — Live',
};

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
  processed_at: number | null;
};

async function getCoopListings(): Promise<{ rows: CoopRow[]; dbUp: boolean }> {
  const db = getDb();
  if (!db) return { rows: [], dbUp: false };
  try {
    const docs = await db
      .collection<Document>('listings')
      // Co-op RENTALS have a low €/m² and no purchase price, so the purchase-tuned
      // map filters don't apply here — just show valid co-op units, newest first.
      // Builder-direct only: Willhaben-sourced rows are excluded because they link
      // to Willhaben (not the builder's reservation page) and can leak mis-tagged
      // for-sale (Eigentum) units onto this rentals-only page.
      // buyable:false is a POSITIVE rental confirmation the poller stamps on every
      // unit it emits (buy-option units are dropped at scrape). Requiring it (not
      // just $ne:true) also hides legacy rows scraped before this flag existed —
      // they reappear within one poll cycle once re-scraped as rentals.
      .find({ is_genossenschaft: true, url_is_valid: { $ne: false }, coop_source: { $ne: 'willhaben' }, buyable: false })
      .sort({ processed_at: -1, _id: -1 })
      .limit(100)
      .toArray();
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
        processed_at: typeof d.processed_at === 'number' ? d.processed_at : null,
      };
    });
    return { rows, dbUp: true };
  } catch {
    return { rows: [], dbUp: false };
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

type Search = { bezirk?: string; minRooms?: string; maxRent?: string };

export default async function CoopPage({
  searchParams,
}: {
  searchParams: Promise<Search>;
}) {
  const { rows, dbUp } = await getCoopListings();
  const sp = await searchParams;

  // Filter controls are pure GET params (SSR, no client JS): the district
  // dropdown is built from the districts actually present, so it never offers an
  // empty result.
  const bezirk = typeof sp.bezirk === 'string' ? sp.bezirk : '';
  const minRooms = Number(sp.minRooms) || 0;
  const maxRent = Number(sp.maxRent) || 0;
  const districts = [...new Set(rows.map((r) => r.bezirk).filter(Boolean))].sort() as string[];

  const filtered = rows.filter(
    (r) =>
      (!bezirk || r.bezirk === bezirk) &&
      (!minRooms || (r.rooms ?? 0) >= minRooms) &&
      (!maxRent || r.price_total == null || r.price_total <= maxRent),
  );

  const inputCls =
    'rounded-lg border border-[#E8E4E0] bg-white px-3 py-1.5 text-sm text-[#2D2D2D]';

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
          className="mt-4 flex flex-wrap items-center gap-2"
        >
          <select name="bezirk" defaultValue={bezirk} data-testid="filter-bezirk" className={inputCls}>
            <option value="">Alle Bezirke</option>
            {districts.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
          <select
            name="minRooms"
            defaultValue={minRooms ? String(minRooms) : ''}
            data-testid="filter-rooms"
            className={inputCls}
          >
            <option value="">Zimmer (alle)</option>
            <option value="1">ab 1 Zimmer</option>
            <option value="2">ab 2 Zimmer</option>
            <option value="3">ab 3 Zimmer</option>
            <option value="4">ab 4 Zimmer</option>
          </select>
          <input
            name="maxRent"
            type="number"
            min="0"
            step="50"
            defaultValue={maxRent ? String(maxRent) : ''}
            placeholder="Max. Miete €"
            data-testid="filter-maxrent"
            className={`${inputCls} w-32`}
          />
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
        </form>

        <p className="mt-3 text-sm font-medium text-[#3D405B]" data-testid="coop-count">
          {filtered.length} {filtered.length === 1 ? 'Treffer' : 'Treffer'}
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
