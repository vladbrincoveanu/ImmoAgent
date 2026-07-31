'use client';

import { useCallback, useEffect, useState } from 'react';

/** Alert dashboard: create a keyword watch on the private-Weitergabe feed and
 * choose where hits land.
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
  if (a.keywords?.length) return a.keywords;
  return a.keyword ? [a.keyword] : [];
}

function describeFilters(f: Alert['filters']): string {
  if (!f) return '';
  const parts: string[] = [];
  if (f.min_area || f.max_area) parts.push(`${f.min_area ?? '–'}–${f.max_area ?? '–'} m²`);
  if (f.min_rooms || f.max_rooms) parts.push(`${f.min_rooms ?? '–'}–${f.max_rooms ?? '–'} Zi.`);
  if (f.max_price) parts.push(`≤ ${f.max_price} €`);
  return parts.join(' · ');
}

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [keyword, setKeyword] = useState('');
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
  // null = entitlement not known yet, so neither the form nor the unlock box
  // flashes before /api/me answers.
  const [isPro, setIsPro] = useState<boolean | null>(null);
  const [password, setPassword] = useState('');
  const [unlocking, setUnlocking] = useState(false);

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

  const loadEntitlement = useCallback(async () => {
    try {
      const res = await fetch('/api/me', { cache: 'no-store' });
      const json = await res.json().catch(() => ({}));
      // An unreachable /api/me must not claim Pro — the server gate decides
      // anyway, and assuming false only costs one visible unlock box.
      setIsPro(res.ok ? Boolean(json.is_pro) : false);
    } catch {
      setIsPro(false);
    }
  }, []);

  useEffect(() => {
    void load();
    void loadEntitlement();
  }, [load, loadEntitlement]);

  /** Trade the shared password for the Pro flag on this browser's user id. The
   * password is only ever checked server-side; a wrong one changes nothing. */
  async function unlock(e: React.FormEvent) {
    e.preventDefault();
    setUnlocking(true);
    setStatus(null);
    try {
      const res = await fetch('/api/unlock', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ password }),
      });
      const json = await res.json().catch(() => ({}));
      if (res.ok) {
        setIsPro(true);
        setPassword('');
        setStatus('Freigeschaltet — Alerts sind jetzt nutzbar.');
      } else if (res.status === 401) {
        setStatus('Falsches Passwort.');
      } else if (res.status === 429) {
        setStatus('Zu viele Versuche — bitte später erneut probieren.');
      } else if (json.error === 'unlock_not_configured') {
        setStatus('Kein Passwort hinterlegt (PRO_UNLOCK_PASSWORD fehlt).');
      } else {
        setStatus('Freischalten fehlgeschlagen.');
      }
    } catch {
      setStatus('Netzwerkfehler beim Freischalten.');
    } finally {
      setUnlocking(false);
    }
  }

  async function create(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setStatus(null);
    try {
      const res = await fetch('/api/saved-searches/alert', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          kind: 'keyword',
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
        setStatus(json.message ?? 'Alert angelegt.');
        setKeyword('');
        setMinArea('');
        setMaxArea('');
        setMinRooms('');
        setMaxRooms('');
        setMaxPrice('');
        setEmail('');
        setChatId('');
        void load();
      } else if (res.status === 402) {
        // The cookie may have been Pro when the page loaded but is not now;
        // surfacing the unlock box beats a dead end.
        setIsPro(false);
        setStatus('Alerts sind Pro-only — bitte unten freischalten.');
      } else {
        setStatus(json.error ?? 'Alert konnte nicht angelegt werden.');
      }
    } catch {
      setStatus('Netzwerkfehler — bitte erneut versuchen.');
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
        setStatus(json.error ?? 'Löschen fehlgeschlagen.');
      }
    } catch {
      setStatus('Netzwerkfehler beim Löschen.');
    }
  }

  /** Prove the chat id works now, rather than discovering at 02:00 that every
   * hit was sent into a chat the bot cannot reach. */
  async function sendTest(id: string) {
    setStatus(null);
    try {
      const res = await fetch('/api/saved-searches/alert/test', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id }),
      });
      const json = await res.json().catch(() => ({}));
      setStatus(res.ok
        ? 'Testnachricht gesendet.'
        : (json.error ?? 'Test fehlgeschlagen.'));
    } catch {
      setStatus('Netzwerkfehler beim Test.');
    }
  }

  return (
    <main className="mx-auto max-w-2xl px-4 py-8" data-testid="alerts-page">
      <h1 className="text-2xl font-bold text-[#3D405B]">Alerts</h1>
      <p className="mt-1 text-sm text-[#6B6B6B]">
        Stichwort-Alarm auf neu erschienene Inserate. Der Poller läuft alle
        2&nbsp;Min.; von der Anzeige bis Telegram vergehen typisch
        2–3&nbsp;Min.
      </p>

      {isPro === false && (
        <form
          onSubmit={unlock}
          data-testid="unlock-form"
          className="mt-6 space-y-3 rounded-xl border border-[#E8C97A] bg-[#FDF7E7] p-4"
        >
          <p className="text-sm font-medium text-[#3D405B]">
            Alerts sind Pro. Mit dem Zugangspasswort freischalten:
          </p>
          <div className="flex gap-2">
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Zugangspasswort"
              aria-label="Zugangspasswort"
              data-testid="unlock-password"
              autoComplete="current-password"
              className={`${inputCls} flex-1`}
            />
            <button
              type="submit"
              disabled={unlocking || !password}
              data-testid="unlock-submit"
              className="rounded-lg bg-[#3D405B] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
            >
              {unlocking ? 'Prüfe…' : 'Freischalten'}
            </button>
          </div>
          <p className="text-xs text-[#6B6B6B]">
            Gilt für diesen Browser (Cookie). In einem anderen Browser oder nach
            dem Löschen der Cookies erneut eingeben.
          </p>
        </form>
      )}

      <form
        onSubmit={create}
        data-testid="alert-form"
        className="mt-6 space-y-3 rounded-xl border border-[#E8E4E0] bg-white p-4"
      >
        <input
          type="text"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          placeholder="Stichwörter, kommagetrennt — z. B. Ablöse, Nachmieter, 1100"
          aria-label="Stichwörter"
          data-testid="alert-keywords"
          className={`${inputCls} w-full`}
        />
        <p className="text-xs text-[#6B6B6B]">
          Ein Treffer genügt: sobald EINES der Stichwörter im Titel oder im
          Anzeigentext vorkommt, wird gemeldet. Ohne Stichwort kommt jede neue
          Anzeige.
        </p>

        <div className="grid grid-cols-2 gap-3">
          <input type="number" min="0" value={minArea}
            onChange={(e) => setMinArea(e.target.value)}
            placeholder="Größe ab (m²)" aria-label="Größe ab"
            data-testid="alert-min-area" className={inputCls} />
          <input type="number" min="0" value={maxArea}
            onChange={(e) => setMaxArea(e.target.value)}
            placeholder="Größe bis (m²)" aria-label="Größe bis"
            data-testid="alert-max-area" className={inputCls} />
          <input type="number" min="0" step="0.5" value={minRooms}
            onChange={(e) => setMinRooms(e.target.value)}
            placeholder="Zimmer ab" aria-label="Zimmer ab"
            data-testid="alert-min-rooms" className={inputCls} />
          <input type="number" min="0" step="0.5" value={maxRooms}
            onChange={(e) => setMaxRooms(e.target.value)}
            placeholder="Zimmer bis" aria-label="Zimmer bis"
            data-testid="alert-max-rooms" className={inputCls} />
          <input type="number" min="0" value={maxPrice}
            onChange={(e) => setMaxPrice(e.target.value)}
            placeholder="Preis max (€)" aria-label="Preis max"
            data-testid="alert-max-price" className={`${inputCls} col-span-2`} />
        </div>
        <p className="text-xs text-[#6B6B6B]">
          Leer lassen heißt „egal“. Fehlt eine Angabe im Inserat, wird trotzdem
          gemeldet — markiert als ungeprüft. Lieber ein Treffer zu viel als
          einer zu spät.
        </p>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="E-Mail (optional)"
          aria-label="E-Mail"
          data-testid="alert-email"
          className={`${inputCls} w-full`}
        />
        <input
          type="text"
          value={chatId}
          onChange={(e) => setChatId(e.target.value)}
          placeholder="Telegram Chat-ID (optional, z. B. -1001234567890)"
          aria-label="Telegram Chat-ID"
          data-testid="alert-chatid"
          className={`${inputCls} w-full`}
        />
        <p className="text-xs text-[#6B6B6B]">
          Mindestens ein Kanal ist nötig. E-Mail muss bestätigt werden, Telegram
          nicht — eine Chat-ID anzugeben ist bereits die Zustimmung.
        </p>
        <button
          type="submit"
          disabled={busy}
          data-testid="alert-submit"
          className="rounded-lg bg-[#3D405B] px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
        >
          {busy ? 'Speichern…' : 'Alert anlegen'}
        </button>
        {status && (
          <p data-testid="alert-status" className="text-sm text-[#2D2D2D]">
            {status}
          </p>
        )}
      </form>

      <h2 className="mt-8 text-lg font-semibold text-[#3D405B]">Aktive Alerts</h2>
      {!loaded ? (
        <p className="mt-2 text-sm text-[#6B6B6B]">Lade…</p>
      ) : alerts.length === 0 ? (
        <p data-testid="alerts-empty" className="mt-2 text-sm text-[#6B6B6B]">
          Noch keine Alerts angelegt.
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
                {keysOf(a).join(', ') || '(alle Treffer)'}
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
                {a.email ? `E-Mail${a.confirmed ? '' : ' (unbestätigt)'}` : null}
              </span>
              <span className="ml-2 inline-flex gap-2">
                <button
                  type="button"
                  data-testid="alert-test"
                  onClick={() => void sendTest(a._id)}
                  className="rounded border border-[#E8E4E0] px-2 py-1 text-xs text-[#3D405B]"
                >
                  Test
                </button>
                <button
                  type="button"
                  data-testid="alert-delete"
                  onClick={() => void remove(a._id)}
                  className="rounded border border-[#E8E4E0] px-2 py-1 text-xs text-[#B23A3A]"
                >
                  Löschen
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
