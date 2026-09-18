export type AlertFilters = {
  min_area?: number;
  max_area?: number;
  min_rooms?: number;
  max_rooms?: number;
  max_price?: number;
};

export type Alert = {
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

export function parseKeywords(raw: string): string[] {
  return raw.split(',').map((key) => key.trim()).filter(Boolean).slice(0, 10);
}

export function numericValue(raw: string): number | undefined {
  const value = Number(raw);
  return raw.trim() && Number.isFinite(value) ? value : undefined;
}

export function keysOf(alert: Alert): string[] {
  if (alert.keywords?.length) return alert.keywords;
  return alert.keyword ? [alert.keyword] : [];
}

export function describeFilters(filters: Alert['filters']): string {
  if (!filters) return '';
  const parts: string[] = [];
  if (filters.min_area || filters.max_area) {
    parts.push(`${filters.min_area ?? '–'}–${filters.max_area ?? '–'} m²`);
  }
  if (filters.min_rooms || filters.max_rooms) {
    parts.push(`${filters.min_rooms ?? '–'}–${filters.max_rooms ?? '–'} Zi.`);
  }
  if (filters.max_price) parts.push(`≤ ${filters.max_price} €`);
  return parts.join(' · ');
}
