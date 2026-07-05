'use client';

import React, { useState } from 'react';
import { useSearchParams } from 'next/navigation';

interface EmailAlertsModalProps {
  open: boolean;
  onClose: () => void;
}

export function EmailAlertsModal({ open, onClose }: EmailAlertsModalProps) {
  const searchParams = useSearchParams();
  const [email, setEmail] = useState('');
  const [frequency, setFrequency] = useState<'instant' | 'daily' | 'weekly'>('daily');
  const [status, setStatus] = useState<'idle' | 'sending' | 'success' | 'error' | 'paywall' | 'paywall_sent'>('idle');
  const [error, setError] = useState<string | null>(null);

  if (!open) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus('sending');
    setError(null);
    const params: Record<string, string> = {};
    searchParams.forEach((v, k) => { params[k] = v; });
    try {
      const res = await fetch('/api/saved-searches/alert', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, params, frequency }),
      });
      if (res.status === 402) {
        setStatus('paywall');
        return;
      }
      if (!res.ok) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.error || 'Subscription failed');
      }
      setStatus('success');
      setTimeout(onClose, 1800);
    } catch (e) {
      setError((e as Error).message);
      setStatus('error');
    }
  };

  return (
    <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6" onClick={(e) => e.stopPropagation()} data-testid="email-alerts-modal">
        <h2 className="text-lg font-semibold text-gray-900 mb-1">Get email alerts for this search</h2>
        <p className="text-sm text-gray-500 mb-4">
          We'll email you when new listings match your current filters (profile, district, price, etc.).
        </p>
        {status === 'success' ? (
          <div className="p-4 rounded-md bg-green-50 text-green-800 text-sm" data-testid="alerts-success">
            ✓ Subscribed! Check your inbox to confirm.
          </div>
        ) : status === 'paywall' || status === 'paywall_sent' ? (
          <div className="space-y-3" data-testid="alerts-paywall">
            <div className="inline-flex items-center gap-1 rounded-full bg-amber-100 text-amber-800 px-2.5 py-0.5 text-xs font-semibold">
              ★ Pro
            </div>
            {status === 'paywall_sent' ? (
              <div className="p-4 rounded-md bg-green-50 text-green-800 text-sm" data-testid="alerts-paywall-success">
                ✓ You&apos;re on the early-access list. We&apos;ll unlock Pro for you and email you at {email}.
              </div>
            ) : (
              <>
                <p className="text-sm text-gray-600">
                  Email alerts are a Pro feature (€19/mo). Request early access and we&apos;ll unlock it for you.
                </p>
                <button
                  type="button"
                  onClick={async () => {
                    const r = await fetch('/api/upgrade', {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ email, reason: 'alerts_pro_only' }),
                    });
                    if (r.ok) setStatus('paywall_sent');
                  }}
                  className="w-full rounded-md bg-blue-600 text-white px-4 py-2 text-sm hover:bg-blue-700"
                  data-testid="alerts-paywall-submit"
                >
                  Request Pro access
                </button>
              </>
            )}
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-3">
            <div>
              <label className="block text-sm font-medium text-gray-700">Email</label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                placeholder="you@example.com"
                data-testid="alerts-email"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700">Frequency</label>
              <select
                value={frequency}
                onChange={(e) => setFrequency(e.target.value as 'instant' | 'daily' | 'weekly')}
                className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm"
                data-testid="alerts-frequency"
              >
                <option value="instant">Instant — as soon as new listings match</option>
                <option value="daily">Daily — once a day digest</option>
                <option value="weekly">Weekly — every Monday</option>
              </select>
            </div>
            {error && <p className="text-sm text-red-600" data-testid="alerts-error">{error}</p>}
            <div className="flex gap-2 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="flex-1 rounded-md border border-gray-300 px-4 py-2 text-sm hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                type="submit"
                disabled={status === 'sending'}
                className="flex-1 rounded-md bg-blue-600 text-white px-4 py-2 text-sm hover:bg-blue-700 disabled:opacity-50"
                data-testid="alerts-submit"
              >
                {status === 'sending' ? 'Subscribing…' : 'Subscribe'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
