'use client';

import React, { useState } from 'react';

export type PaywallReason = 'saved_search_limit' | 'alerts_pro_only' | 'pro_profiles';

interface PaywallModalProps {
  open: boolean;
  reason: PaywallReason;
  onClose: () => void;
}

const COPY: Record<PaywallReason, { title: string; body: string }> = {
  saved_search_limit: {
    title: 'Saved search limit reached',
    body: 'The free plan includes 3 saved searches. Pro (€19/mo) unlocks unlimited saved searches and email alerts.',
  },
  alerts_pro_only: {
    title: 'Email alerts are a Pro feature',
    body: 'Pro (€19/mo) sends you new matching listings by email and unlocks unlimited saved searches.',
  },
  pro_profiles: {
    title: 'Buyer personas are a Pro feature',
    body: 'Pro (€19/mo) unlocks persona-based rankings — First-Time Buyer, Growing Family, Renovator/Investor, and Urban Professional each re-rank every listing for that buyer.',
  },
};

export function PaywallModal({ open, reason, onClose }: PaywallModalProps) {
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState<'idle' | 'sending' | 'success' | 'error'>('idle');

  if (!open) return null;
  const copy = COPY[reason];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setStatus('sending');
    try {
      const res = await fetch('/api/upgrade', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, reason }),
      });
      if (!res.ok) throw new Error('Request failed');
      setStatus('success');
    } catch {
      setStatus('error');
    }
  };

  return (
    <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/50" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6" onClick={(e) => e.stopPropagation()} data-testid="paywall-modal">
        <div className="inline-flex items-center gap-1 rounded-full bg-amber-100 text-amber-800 px-2.5 py-0.5 text-xs font-semibold mb-3">
          ★ Pro
        </div>
        <h2 className="text-lg font-semibold text-gray-900 mb-1">{copy.title}</h2>
        <p className="text-sm text-gray-500 mb-4">{copy.body}</p>
        {status === 'success' ? (
          <div className="p-4 rounded-md bg-green-50 text-green-800 text-sm" data-testid="paywall-success">
            ✓ You&apos;re on the early-access list. We&apos;ll unlock Pro for you and email you at {email}.
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
                data-testid="paywall-email"
              />
            </div>
            {status === 'error' && (
              <p className="text-sm text-red-600" data-testid="paywall-error">Something went wrong — try again.</p>
            )}
            <div className="flex gap-2 pt-2">
              <button
                type="button"
                onClick={onClose}
                className="flex-1 rounded-md border border-gray-300 px-4 py-2 text-sm hover:bg-gray-50"
              >
                Not now
              </button>
              <button
                type="submit"
                disabled={status === 'sending'}
                className="flex-1 rounded-md bg-blue-600 text-white px-4 py-2 text-sm hover:bg-blue-700 disabled:opacity-50"
                data-testid="paywall-submit"
              >
                {status === 'sending' ? 'Sending…' : 'Request Pro access'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
