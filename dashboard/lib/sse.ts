import { useEffect, useRef, useState } from 'react';

export interface SSENewListing {
  _id: string;
  title: string;
  url?: string;
  source_enum?: string;
  bezirk?: string;
  price_total?: number | null;
  area_m2?: number | null;
  rooms?: number | null;
  score?: number | null;
  image_url?: string | null;
}

export function useListingsSSE() {
  const [newListings, setNewListings] = useState<SSENewListing[]>([]);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    let mounted = true;

    const connect = () => {
      const eventSource = new EventSource('/api/listings/stream');
      eventSourceRef.current = eventSource;

      eventSource.onmessage = (event) => {
        if (!mounted) return;
        try {
          const parsed = JSON.parse(event.data);
          if (parsed.type === 'new_listing' && parsed.data) {
            setNewListings((prev) => {
              const exists = prev.some((l) => l._id === parsed.data._id);
              if (exists) return prev;
              return [parsed.data, ...prev];
            });
          }
        } catch {
          // Ignore parse errors
        }
      };

      eventSource.onerror = () => {
        if (!mounted) return;
        setError('SSE connection lost');
        eventSource.close();
        // Reconnect after 5 seconds
        setTimeout(() => {
          if (mounted) {
            connect();
          }
        }, 5000);
      };
    };

    connect();

    return () => {
      mounted = false;
      eventSourceRef.current?.close();
    };
  }, []);

  return { newListings, error };
}