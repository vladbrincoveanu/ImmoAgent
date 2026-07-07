'use client';

import { useEffect, useRef } from 'react';

interface LayerState {
  listings: boolean;
  stations: boolean;
  schools: boolean;
  heatmap: boolean;
}

interface MapLayersPopoverProps {
  open: boolean;
  onClose: () => void;
  layers: LayerState;
  onToggle: (key: 'listings' | 'stations' | 'schools' | 'heatmap') => void;
  counts: { listings: number; stations: number; schools: number; heatmap: number };
}

const ROWS: Array<{ key: 'listings' | 'stations' | 'schools' | 'heatmap'; name: string; color: string; dotColor: string }> = [
  { key: 'listings', name: 'Listings', color: '#16243a', dotColor: 'bg-ink' },
  { key: 'stations', name: 'U-Bahn stations', color: '#3b6fd4', dotColor: 'bg-[#3b6fd4]' },
  { key: 'schools', name: 'Schools', color: '#2ba56b', dotColor: 'bg-[#2ba56b]' },
  { key: 'heatmap', name: 'District prices', color: '#d73027', dotColor: 'bg-[#d73027]' },
];

export function MapLayersPopover({ open, onClose, layers, onToggle, counts }: MapLayersPopoverProps) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      const t = e.target as Element;
      // Let the Layers button handle its own toggle — avoids close-then-reopen
      if (t.closest('[data-testid="layers-btn"]')) return;
      if (ref.current && !ref.current.contains(t)) onClose();
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div
      ref={ref}
      data-testid="layers-popover"
      className="absolute top-[42px] right-0 w-[224px] bg-card border border-line rounded-xl shadow-[0_12px_32px_rgba(22,36,58,0.14)] p-2 z-[1100]"
      onClick={(e) => e.stopPropagation()}
    >
      {ROWS.map((row) => {
        const on = layers[row.key];
        return (
          <div
            key={row.key}
            data-testid={`layer-row-${row.key}`}
            onClick={() => onToggle(row.key)}
            className={`flex items-center gap-2.5 px-2.5 py-2 rounded-lg cursor-pointer text-[13px] hover:bg-bg ${
              on ? 'bg-bg' : ''
            }`}
          >
            <span className={`w-2 h-2 rounded-full flex-shrink-0 ${row.dotColor}`} />
            <span className="flex-1">{row.name}</span>
            <span className="text-[11.5px] text-ink-3">{counts[row.key]}</span>
            <span
              data-testid={`layer-toggle-${row.key}`}
              className={`w-8 h-[18px] rounded-full relative transition-colors ${
                on ? 'bg-accent' : 'bg-[#d6dde6]'
              }`}
            >
              <span
                className={`absolute top-0.5 w-3.5 h-3.5 rounded-full bg-white shadow-sm transition-all ${
                  on ? 'left-4' : 'left-0.5'
                }`}
              />
            </span>
          </div>
        );
      })}
    </div>
  );
}
