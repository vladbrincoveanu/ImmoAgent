'use client';

import { useCallback, useEffect, useState } from 'react';

/** Alert dashboard: create a keyword watch on the private-Weitergabe feed and
 * choose where hits land.
 *
 * Client component because the whole page is a form with live feedback, and the
 * create/delete round trips need to update the list without a reload — a co-op
 * alert is usually set up in a hurry. */

type Alert = {
  _id: string;
  kind: string;
  keyword: string | null;
  email: string | null;
  telegram_chat_id: string | null;
  confirmed: boolean;
  created_at: string | null;
};

const inputCls =
  'rounded-lg border border-[#E8E4E0] bg-white px-3 py-2 text-sm text-[#2D2D2D]';

export default function AlertsPage() {
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [keyword, setKeyword] = useState('');
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
          kind: 'coop_private',
          keyword,
          email: email || undefined,
          telegram_chat_id: chatId || undefined,
          frequency: 'instant',
        }),
      });
      const json = await res.json().catch(() => ({}));
      if (res.ok) {
        setStatus(json.message ?? 'Alert angelegt.');
        setKeyword('');
        setEmail('');
        setChatId('');
        void load();
      } else if (res.status === 402) {
        setStatus('Alerts sind Pro-only — bitte Upgrade durchführen.');
      } else {
        setStatus(json.error ?? 'Alert konnte nicht angelegt werden.');
      }
    } catch {
      setStatus('Netzwerkfehler — bitte erneut versuchen.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-2xl px-4 py-8" data-testid="alerts-page">
      <h1 className="text-2xl font-bold text-[#3D405B]">Alerts</h1>
      <p className="mt-1 text-sm text-[#6B6B6B]">
        Stichwort-Alarm auf private Genossenschafts-Weitergaben. Treffer kommen
        sofort — der Poller läuft alle 2&nbsp;Min. zwischen 06:00 und 17:00 Uhr.
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
          maxLength={80}
          placeholder="Stichwort, z. B. 1100 oder Balkon"
          aria-label="Stichwort"
          data-testid="alert-keyword"
          className={`${inputCls} w-full`}
        />
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
                {a.keyword || '(alle Treffer)'}
              </span>
              <span className="text-[#6B6B6B]">
                {' · '}
                {a.telegram_chat_id ? 'Telegram' : null}
                {a.telegram_chat_id && a.email ? ' + ' : null}
                {a.email ? `E-Mail${a.confirmed ? '' : ' (unbestätigt)'}` : null}
              </span>
            </li>
          ))}
        </ul>
      )}
    </main>
  );
}
