'use client';

import React from 'react';
import { useSearchParams, useRouter, usePathname } from 'next/navigation';
import { PROFILES, DEFAULT_PROFILE } from '@/lib/profile';

export function ProfileSelector() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const current = searchParams.get('profile') ?? DEFAULT_PROFILE;

  const handleChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const next = e.target.value;
    const params = new URLSearchParams(searchParams.toString());
    if (next === DEFAULT_PROFILE) {
      params.delete('profile');
    } else {
      params.set('profile', next);
    }
    const qs = params.toString();
    router.push(qs ? `${pathname}?${qs}` : pathname);
  };

  return (
    <div className="flex items-center gap-2">
      <label className="text-sm font-medium text-gray-700">Buyer Profile</label>
      <select
        data-testid="profile-selector"
        value={current}
        onChange={handleChange}
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
