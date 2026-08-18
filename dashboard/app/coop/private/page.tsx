import { getDb } from '@/lib/mongodb';
import { Document } from 'mongodb';
import { privateCoopQuery } from '@/lib/coop-query';
import { CoopThumb } from '@/components/CoopThumb';
import { CoopTabs } from '@/components/CoopTabs';

// Always fresh: these are first-come-first-served ads polled by an external
// minutely trigger, and a cached page here is worse than no page. End-to-end
// notification latency is typically 2–3 minutes because GitHub runner startup
// and delivery are on the critical path.
export const dynamic = 'force-dynamic';

export const metadata = {
  title: 'Private co-op transfers — live',
};

type PrivateRow = {
  url: string;
  title: string | null;
  address: string | null;
  bezirk: string | null;
  rooms: number | null;
  area_m2: number | null;
  price_total: number | null;
  image_url: string | null;
  description: string | null;
  first_seen_at: string | null;
};

const ROW_LIMIT = 200;
const Q_MAX_LEN = 80;

/** User input is interpolated into a Mongo `$regex`, so every metacharacter has
 * to be neutralised first — unescaped, `(a+)+$` is catastrophic backtracking
 * against every row the base query admits. Same guard as /coop. */
function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

// en-GB grouping to match the English UI — see the same note on /coop.
function fmtInt(n: number | null): string {
  return n == null ? '—' : new Intl.NumberFormat('en-GB').format(Math.round(n));
}

function fmtArea(n: number | null): string {
  return n == null ? '—' : `${new Intl.NumberFormat('en-GB').format(Math.round(n))} m²`;
}

function buildQuery(q: string, bezirk: string): Document {
  const and: Document[] = [privateCoopQuery()];
  if (bezirk) and.push({ bezirk });
  if (q) {
    // Across title, address AND the ad body. Body matters most here: "Nachmieter
    // gesucht" or "Ablöse VB" is usually buried in the description, not the title,
    // so a title-only search would miss most of the feed.
    const rx = { $regex: escapeRegex(q), $options: 'i' };
    and.push({ $or: [{ title: rx }, { address: rx }, { description: rx }] });
  }
  return and.length === 1 ? and[0] : { $and: and };
}

export default async function PrivateCoopPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const sp = await searchParams;
  const first = (v: string | string[] | undefined): string =>
    (Array.isArray(v) ? v[0] : v) ?? '';
  const q = first(sp.q).slice(0, Q_MAX_LEN);
  const bezirk = first(sp.bezirk);

  const db = getDb();
  let rows: PrivateRow[] = [];
  let dbDown = false;

  if (!db) {
    dbDown = true;
  } else {
    try {
      const docs = await db
        .collection('listings')
        .find(buildQuery(q, bezirk))
        // Newest first: on a first-come-first-served feed, the top of the list is
        // the only part with any value.
        .sort({ first_seen_at: -1, processed_at: -1 })
        .limit(ROW_LIMIT)
        .toArray();
      rows = docs.map((d) => ({
        url: d.url as string,
        title: (d.title as string) ?? null,
        address: (d.address as string) ?? null,
        bezirk: (d.bezirk as string) ?? null,
        rooms: (d.rooms as number) ?? null,
        area_m2: (d.area_m2 as number) ?? null,
        price_total: (d.price_total as number) ?? null,
        image_url: (d.image_url as string) ?? null,
        description: (d.description as string) ?? null,
        first_seen_at: (d.first_seen_at as string) ?? null,
      }));
    } catch (err) {
      console.error('[/coop/private]', err);
      dbDown = true;
    }
  }

  const districts = Array.from(
    new Set(rows.map((r) => r.bezirk).filter((b): b is string => !!b)),
  ).sort();

  const inputCls =
    'rounded-lg border border-[#E8E4E0] bg-white px-3 py-1.5 text-sm text-[#2D2D2D]';

  return (
    <main className="mx-auto max-w-4xl px-4 py-8" data-testid="coop-private-page">
      <div className="mb-6">
        <CoopTabs active="private" />
        <h1 className="text-2xl font-bold text-[#3D405B]">
          Private co-op transfers
        </h1>
        <p className="mt-1 text-sm text-[#6B6B6B]">
          Flats passed on directly by their tenants — no waiting list,{' '}
          <strong>first come first served</strong>. Source: Willhaben · Vienna ·
          polled every minute by an external trigger; notifications typically
          arrive in 2–3 minutes.
        </p>
        <p className="mt-1 text-xs text-[#6B6B6B]">
          A hit needs both a transfer signal (Ablöse, Nachmieter, Weitergabe) and
          a co-op signal — a kitchen buy-out in a privately financed flat does not
          land here.
        </p>

        <form
          method="get"
          data-testid="private-filters"
          className="mt-4 flex flex-wrap gap-2 rounded-xl border border-[#E8E4E0] bg-white p-4"
        >
          <select
            name="bezirk"
            defaultValue={bezirk}
            data-testid="private-filter-bezirk"
            className={inputCls}
          >
            <option value="">All districts</option>
            {districts.map((d) => (
              <option key={d} value={d}>
                {d}
              </option>
            ))}
          </select>
          <input
            type="search"
            name="q"
            defaultValue={q}
            maxLength={Q_MAX_LEN}
            placeholder="Title, address or ad text…"
            aria-label="Search title, address or ad text"
            data-testid="private-filter-q"
            className={`${inputCls} min-w-[15rem] flex-1`}
          />
          <button
            type="submit"
            data-testid="private-filter-apply"
            className="rounded-lg bg-[#3D405B] px-3 py-1.5 text-sm font-medium text-white"
          >
            Filter
          </button>
          <a
            href="/coop/private"
            data-testid="private-filter-reset"
            className="px-2 py-1.5 text-sm text-[#6B6B6B] underline"
          >
            Reset
          </a>
        </form>
      </div>

      {dbDown ? (
        <p data-testid="private-db-error" className="text-sm text-[#B4654A]">
          Database unreachable — please try again later.
        </p>
      ) : rows.length === 0 ? (
        <p data-testid="private-empty" className="text-sm text-[#6B6B6B]">
          No private transfers found right now.
        </p>
      ) : (
        <ul className="space-y-2" data-testid="private-list">
          {rows.map((r) => (
            <li key={r.url} data-testid="private-item">
              <a
                href={r.url}
                target="_blank"
                rel="noopener noreferrer"
                className="block rounded-lg border border-[#E8E4E0] bg-white px-4 py-3 transition-colors hover:bg-[#FBFAF8]"
              >
                <div className="flex items-start gap-3">
                  <CoopThumb src={r.image_url} bezirk={r.bezirk} />
                  <div className="min-w-0 flex-1">
                    <div
                      className="truncate font-semibold text-[#3D405B]"
                      data-testid="private-title"
                    >
                      {r.title || r.address || 'Co-op flat'}
                    </div>
                    <div className="mt-1 text-sm text-[#2D2D2D]" data-testid="private-specs">
                      <span>{r.rooms != null ? `${Math.round(r.rooms)} rooms` : '—'}</span>
                      {' · '}
                      <span>{fmtArea(r.area_m2)}</span>
                      {' · '}
                      <span className="font-medium">
                        {r.price_total != null ? `€${fmtInt(r.price_total)} rent` : 'rent —'}
                      </span>
                    </div>
                  </div>
                </div>
              </a>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
