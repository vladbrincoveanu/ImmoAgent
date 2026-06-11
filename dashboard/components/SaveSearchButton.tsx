'use client';

import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';

interface SavedSearch {
  _id: string;
  name: string;
  params: Record<string, string>;
  created_at: string;
}

export function SaveSearchButton() {
  const searchParams = useSearchParams();
  const [saved, setSaved] = useState(false);
  const [list, setList] = useState<SavedSearch[]>([]);
  const [open, setOpen] = useState(false);

  const refresh = async () => {
    try {
      const res = await fetch('/api/saved-searches');
      const data = await res.json();
      setList(data.items ?? []);
    } catch {}
  };

  useEffect(() => { refresh(); }, []);

  const handleSave = async () => {
    const paramsObj: Record<string, string> = {};
    searchParams.forEach((v, k) => { paramsObj[k] = v; });
    const name = prompt('Name this search:', `Search ${new Date().toLocaleDateString()}`);
    if (!name) return;
    const res = await fetch('/api/saved-searches', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, params: paramsObj }),
    });
    if (res.ok) {
      setSaved(true);
      await refresh();
      setTimeout(() => setSaved(false), 2000);
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this saved search?')) return;
    await fetch(`/api/saved-searches?id=${id}`, { method: 'DELETE' });
    await refresh();
  };

  const buildQuery = (params: Record<string, string>) => {
    const usp = new URLSearchParams(params);
    return usp.toString();
  };

  return (
    <div className="relative">
      <button
        type="button"
        onClick={handleSave}
        className="inline-flex items-center gap-1.5 rounded-md border border-border bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 hover:border-muted transition-colors"
        data-testid="save-search-btn"
        title="Save current filters as a bookmark"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
        </svg>
        {saved ? 'Saved!' : 'Save search'}
      </button>
      {list.length > 0 && (
        <button
          type="button"
          onClick={() => setOpen(!open)}
          className="ml-1 inline-flex items-center gap-1 rounded-md border border-border bg-white px-2 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50"
          data-testid="saved-searches-toggle"
          aria-label="Show saved searches"
        >
          <span className="text-xs">{list.length}</span>
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
      )}
      {open && list.length > 0 && (
        <div className="absolute right-0 top-full mt-1 w-80 bg-white border border-border rounded-md shadow-lg z-50 max-h-96 overflow-y-auto">
          <div className="p-2 border-b border-border text-xs font-semibold text-muted uppercase tracking-wide">Saved searches</div>
          {list.map((s) => (
            <div key={s._id} className="flex items-center justify-between p-2 hover:bg-gray-50 border-b border-gray-100">
              <a
                href={`/dashboard?${buildQuery(s.params)}`}
                className="flex-1 min-w-0"
              >
                <p className="text-sm font-medium text-text truncate">{s.name}</p>
                <p className="text-[10px] text-muted">{new Date(s.created_at).toLocaleString()}</p>
              </a>
              <button
                onClick={() => handleDelete(s._id)}
                className="ml-2 p-1 text-muted hover:text-red-600"
                aria-label="Delete"
              >
                <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
