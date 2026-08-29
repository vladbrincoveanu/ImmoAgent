'use client';

import { useCallback, useEffect, useState } from 'react';
import { normalizeAlertKeywords } from '@/lib/alert-test';

/** Alert dashboard: create a watch on builder-direct MyGEWO rentals or the
 * private-tenant handover feed, then choose where hits land.
 *
 * Client component because the whole page is a form with live feedback, and the
 * create/delete round trips need to update the list without a reload — a co-op
 * alert is usually set up in a hurry. */

type AlertFilters = {
  min_area?: number; max_area?: number;
  min_rooms?: number; max_rooms?: number;
  max_price?: number;
};

type Alert = {
  _id: string;
  kind: string;
  keywords?: string[] | null;
  keyword?: string | null;
  filters?: AlertFilters | null;
  email: string | null;
  telegram_chat_id: string | null;
  confirmed: boolean;
  created_at: string | null;
};

const inputCls =
  'rounded-lg border border-[#E8E4E0] bg-white px-3 py-2 text-sm text-[#2D2D2D]';

/** "Ablöse, Nachmieter , " → ["Ablöse", "Nachmieter"]. Split on the comma only:
 * a space is legitimate inside a key ("Nachmieter gesucht"). */
function parseKeywords(raw: string): string[] {
  return raw.split(',').map((k) => k.trim()).filter(Boolean).slice(0, 10);
}

/** Blank stays undefined rather than becoming 0 — an unset gate must pass
 * everything, and `max_price: 0` would match nothing at all. */
function num(raw: string): number | undefined {
  const v = Number(raw);
  return raw.trim() && Number.isFinite(v) ? v : undefined;
}

/** The keys an alert watches, tolerating records that only have the old scalar. */
function keysOf(a: Alert): string[] {
  return normalizeAlertKeywords(a);
}

function stringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.filter((item): item is string => (
    typeof item === 'string' && item.length > 0
  ));
}

function errorMessages(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value.map((item) => {
    if (typeof item === 'string') return item;
    if (item && typeof item === 'object' && 'message' in item
      && typeof item.message === 'string') {
      return item.message;
    }
    return '';
  }).filter(Boolean);
}

function describeFilters(f: Alert['filters']): string {
  if (!f) return '';
  const parts: string[] = [];
  if (f.min_area || f.max_area) parts.push(`${f.min_area ?? '–'}–${f.max_area ?? '–'} m²`);
  if (f.min_rooms || f.max_rooms) parts.push(`${f.min_rooms ?? '–'}–${f.max_rooms ?? '–'} rm`);
  if (f.max_price) parts.push(`≤ ${f.max_price} €`);
  return parts.join(' · ');
}

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [keyword, setKeyword] = useState('');
  // The default source is already scoped to builder-direct MyGEWO rentals. The
  // checkbox opts into the separate private-tenant handover rubric.
  const [privateOnly, setPrivateOnly] = useState(false);
  const [minArea, setMinArea] = useState('');
  const [maxArea, setMaxArea] = useState('');
  const [minRooms, setMinRooms] = useState('');
  const [maxRooms, setMaxRooms] = useState('');
  const [maxPrice, setMaxPrice] = useState('');
  const [email, setEmail] = useState('');
  const [chatId, setChatId] = useState('');
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(async () => {
    try {
      const res = await fetch('/api/saved-searches/alert', { cache: 'no-store' });
      if (res.ok) {
        const json = await res.json();
        setAlerts(Array.isArray(json.items) ? json.items : []);
      }
    } catch {
      // A failed list must not blank the create form — the user can still add one.
    } finally {
      setLoaded(true);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setStatus(null);
    try {
      const res = await fetch('/api/saved-searches/alert', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          // 'mygewo' is all builder-direct units; the checkbox opts into the
          // rubric-gated private-tenant handover feed.
          kind: privateOnly ? 'coop_private' : 'mygewo',
          keywords: parseKeywords(keyword),
          filters: {
            min_area: num(minArea), max_area: num(maxArea),
            min_rooms: num(minRooms), max_rooms: num(maxRooms),
            max_price: num(maxPrice),
          },
          email: email || undefined,
          telegram_chat_id: chatId || undefined,
          frequency: 'instant',
        }),
      });
      const json = await res.json().catch(() => ({}));
      if (res.ok) {
        setStatus(json.message ?? 'Alert created.');
        setKeyword('');
        setMinArea('');
        setMaxArea('');
        setMinRooms('');
        setMaxRooms('');
        setMaxPrice('');
        setEmail('');
        setChatId('');
        void load();
      } else {
        setStatus(json.error ?? 'Could not create the alert.');
      }
    } catch {
      setStatus('Network error — please try again.');
    } finally {
      setBusy(false);
    }
  }

  async function remove(id: string) {
    setStatus(null);
    try {
      const res = await fetch(
        `/api/saved-searches/alert?id=${encodeURIComponent(id)}`,
        { method: 'DELETE' });
      if (res.ok) {
        void load();
      } else {
        const json = await res.json().catch(() => ({}));
        setStatus(json.error ?? 'Delete failed.');
      }
    } catch {
      setStatus('Network error while deleting.');
    }
  }

  /** Prove each configured notification channel now, rather than discovering at
   * 02:00 that every hit was sent somewhere the provider cannot reach. */
  async function sendTest(id: string) {
    setStatus(null);
    try {
      const res = await fetch('/api/saved-searches/alert/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id }),
      });
      const json = await res.json().catch(() => ({}));
      const sentChannels = stringList(json.sentChannels);
      const channels = sentChannels.length ? sentChannels : stringList(json.channels);
      const failedChannels = stringList(json.failedChannels);
      const structuredErrors = errorMessages(json.errors);
      const message = res.ok
        ? (typeof json.message === 'string' ? json.message : 'Test notification completed.')
        : (typeof json.error === 'string' ? json.error : 'Test failed.');
      const warning = typeof json.warning === 'string' ? json.warning : '';
      const errorDetails = structuredErrors.join(' ');
      const statusParts = [
        message,
        channels.length ? `Sent via ${channels.join(' and ')}.` : '',
        failedChannels.length ? `Failed channels: ${failedChannels.join(' and ')}.` : '',
        errorDetails && !message.includes(errorDetails) ? errorDetails : '',
        warning,
      ].filter(Boolean);
      setStatus(statusParts.join(' '));
    } catch {
      setStatus('Network error during the test.');
    }
  }

  return (
    <main className="mx-auto max-w-2xl px-4 py-8" data-testid="alerts-page">
      <h1 className="text-2xl font-bold text-[#3D405B]">Alerts</h1>
      <p className="mt-1 text-sm text-[#6B6B6B]">
        Alerts on newly posted co-op ads. cron-job.org triggers the poll every minute;
        expect 2–3&nbsp;min from the ad going live to a Telegram or email notification.
      </p>

      <form
        onSubmit={create}
        data-testid="alert-form"
        className="mt-6 space-y-3 rounded-xl border border-[#E8E4E0] bg-white p-4"
      >
        <input
          type="text"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          placeholder="Keywords, comma-separated — e.g. Ablöse, Nachmieter, 1100"
          aria-label="Keywords"
          data-testid="alert-keywords"
          className={`${inputCls} w-full`}
        />
        <p className="text-xs text-[#6B6B6B]">
          Keywords are optional narrowing filters and one hit is enough: you are
          notified as soon as ANY keyword appears in the title or ad text. Leave
          this empty to get every unit in the selected feed.
        </p>

        <label className="flex items-start gap-2 text-sm text-[#2D2D2D]">
          <input
            type="checkbox"
            checked={privateOnly}
            onChange={(e) => setPrivateOnly(e.target.checked)}
            data-testid="alert-private-only"
            className="mt-0.5"
          />
          <span>
            Private tenant handover only
            <span className="block text-xs text-[#6B6B6B]">
              Requires both a co-op marker and a handover marker (Weitergabe,
              Nachmieter, Ablöse) in the same ad. Keywords alone cannot do this —
              they are OR-ed, so &ldquo;Ablöse&rdquo; on its own would let every
              kitchen buyout through. Leave unchecked to watch all new
              builder-direct MyGEWO rentals.
            </span>
          </span>
        </label>

        <div className="grid grid-cols-2 gap-3">
          <input type="number" min="0" value={minArea}
            onChange={(e) => setMinArea(e.target.value)}
            placeholder="Size from (m²)" aria-label="Size from"
            data-testid="alert-min-area" className={inputCls} />
          <input type="number" min="0" value={maxArea}
            onChange={(e) => setMaxArea(e.target.value)}
            placeholder="Size to (m²)" aria-label="Size to"
            data-testid="alert-max-area" className={inputCls} />
          <input type="number" min="0" step="0.5" value={minRooms}
            onChange={(e) => setMinRooms(e.target.value)}
            placeholder="Rooms from" aria-label="Rooms from"
            data-testid="alert-min-rooms" className={inputCls} />
          <input type="number" min="0" step="0.5" value={maxRooms}
            onChange={(e) => setMaxRooms(e.target.value)}
            placeholder="Rooms to" aria-label="Rooms to"
            data-testid="alert-max-rooms" className={inputCls} />
          <input type="number" min="0" value={maxPrice}
            onChange={(e) => setMaxPrice(e.target.value)}
            placeholder="Max price (€)" aria-label="Max price"
            data-testid="alert-max-price" className={`${inputCls} col-span-2`} />
        </div>
        <p className="text-xs text-[#6B6B6B]">
          Leave a field empty for &ldquo;don&rsquo;t care&rdquo;. If the ad omits
          a value you still get notified — flagged as unverified. Better one hit
          too many than one too late.
        </p>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="Email (optional)"
          aria-label="Email"
          data-testid="alert-email"
          className={`${inputCls} w-full`}
        />
        <input
          type="text"
          value={chatId}
          onChange={(e) => setChatId(e.target.value)}
          placeholder="Telegram chat ID (optional, e.g. -1001234567890)"
          aria-label="Telegram chat ID"
          data-testid="alert-chatid"
          className={`${inputCls} w-full`}
        />
        {/* Spelled out because a bot token pasted here is a real mistake: it
            leaks the token and the id never validates. */}
        <p className="text-xs text-[#6B6B6B]">
          At least one channel is required. Email can be used alone, but it must
          be confirmed before delivery. Telegram does not need confirmation —
          supplying a chat ID is itself the consent. The chat ID is a plain
          number (message @userinfobot to get yours), <strong>not</strong>{' '}
          a bot token — this app uses its own bot.
        </p>
        <button
          type="submit"
          disabled={busy}
          data-testid="alert-submit"
          className="rounded-lg bg-[#3D405B] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
        >
          {busy ? 'Saving…' : 'Create alert'}
        </button>
        {status && (
          <p data-testid="alert-status" className="text-sm text-[#2D2D2D]">
            {status}
          </p>
        )}
      </form>

      <h2 className="mt-8 text-lg font-semibold text-[#3D405B]">Active alerts</h2>
      {!loaded ? (
        <p className="mt-2 text-sm text-[#6B6B6B]">Loading…</p>
      ) : alerts.length === 0 ? (
        <p data-testid="alerts-empty" className="mt-2 text-sm text-[#6B6B6B]">
          No alerts created yet.
        </p>
      ) : (
        <ul className="mt-2 space-y-2" data-testid="alerts-list">
          {alerts.map((a) => (
            <li
              key={a._id}
              data-testid="alert-item"
              className="rounded-lg border border-[#E8E4E0] bg-white px-4 py-3 text-sm"
            >
              <span className="font-medium text-[#3D405B]">
                {keysOf(a).join(', ') || '(all hits)'}
              </span>
              {describeFilters(a.filters) && (
                <span className="text-[#6B6B6B]">
                  {' · '}{describeFilters(a.filters)}
                </span>
              )}
              <span className="text-[#6B6B6B]">
                {' · '}
                {a.telegram_chat_id ? 'Telegram' : null}
                {a.telegram_chat_id && a.email ? ' + ' : null}
                {a.email ? `Email${a.confirmed ? '' : ' (unconfirmed)'}` : null}
              </span>
              <span className="ml-2 inline-flex gap-2">
                <button
                  type="button"
                  data-testid="alert-test"
                  onClick={() => void sendTest(a._id)}
                  className="rounded border border-[#E8E4E0] px-2 py-1 text-xs text-[#3D405B]"
                >
                  Test notification
                </button>
                <button
                  type="button"
                  data-testid="alert-delete"
                  onClick={() => void remove(a._id)}
                  className="rounded border border-[#E8E4E0] px-2 py-1 text-xs text-[#B23A3A]"
                >
                  Delete
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
