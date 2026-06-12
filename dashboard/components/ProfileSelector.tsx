'use client';

import React from 'react';
import { PROFILES, DEFAULT_PROFILE } from '@/lib/profile';

interface ProfileSelectorProps {
  value?: string;
  onChange?: (next: string) => void;
}

export function ProfileSelector({ value, onChange }: ProfileSelectorProps = {}) {
  const current = value ?? DEFAULT_PROFILE;

  return (
    <div className="flex items-center gap-2">
      <label className="text-sm font-medium text-gray-700">Buyer Profile</label>
      <select
        data-testid="profile-selector"
        value={current}
        onChange={(e) => onChange?.(e.target.value)}
        className="rounded-md border border-border bg-white px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-accent text-gray-700"
        aria-label="Buyer profile"
      >
        {PROFILES.map((p) => (
          <option key={p.key} value={p.key} title={p.description}>
            {p.label}
          </option>
        ))}
      </select>
    </div>
  );
}
