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
  buy_option: boolean;
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
      .find({ is_genossenschaft: true, url_is_valid: { $ne: false }, coop_source: { $ne: 'willhaben' } })
      .sort({ processed_at: -1, _id: -1 })
      .limit(100)
      .toArray();
    const rows = docs.map((d): CoopRow => {
      const feats = Array.isArray(d.special_features) ? (d.special_features as string[]) : [];
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
        buy_option: feats.some((f) => /kaufoption/i.test(f)),
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

export default async function CoopPage() {
  const { rows, dbUp } = await getCoopListings();

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
          über alle Bauträger · Filter: ab 3 Zimmer · ab 51 m² · Miete &lt; €1.000 · Wien ·
          Aktualisierung alle 5&nbsp;Min.
        </p>
        <p className="mt-1 text-sm font-medium text-[#3D405B]" data-testid="coop-count">
          {rows.length} {rows.length === 1 ? 'Treffer' : 'Treffer'}
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

      {dbUp && rows.length === 0 && (
        <div
          data-testid="coop-empty"
          className="rounded-lg border border-[#E8E4E0] bg-white px-4 py-8 text-center text-sm text-[#6B6B6B]"
        >
          Aktuell keine passenden Genossenschaftswohnungen. Sobald ein neues Angebot
          erscheint, taucht es hier (und im Telegram-Kanal) auf.
        </div>
      )}

      <ul className="space-y-3" data-testid="coop-list">
        {rows.map((r) => {
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
                    {r.buy_option && (
                      <span
                        data-testid="coop-buyoption"
                        className="rounded bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800"
                      >
                        Kaufoption
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
