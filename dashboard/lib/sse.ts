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

/** Give up after this many failed connects. A permanently broken stream must
 * not reconnect for the whole time the tab is open. */
const MAX_ATTEMPTS = 5;
const BASE_DELAY_MS = 5000;
const MAX_DELAY_MS = 60000;

export function useListingsSSE() {
  const [newListings, setNewListings] = useState<SSENewListing[]>([]);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  useEffect(() => {
    let mounted = true;
    let attempts = 0;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;
    // Set when the server reports the deployment cannot support change streams.
    // That is a configuration fact, so retrying can never succeed.
    let giveUp = false;

    const connect = () => {
      const eventSource = new EventSource('/api/listings/stream');
      eventSourceRef.current = eventSource;

      eventSource.onopen = () => {
        attempts = 0;
      };

      eventSource.onmessage = (event) => {
        if (!mounted) return;
        try {
          const parsed = JSON.parse(event.data);

          if (parsed.type === 'unsupported') {
            giveUp = true;
            setError('Live updates unavailable on this deployment');
            eventSource.close();
            return;
          }

          if (parsed.type === 'error') {
            setError('Live updates interrupted');
            return;
          }

          if (parsed.type === 'new_listing' && parsed.data) {
            setError(null);
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
        eventSource.close();
        if (giveUp) return;

        attempts += 1;
        if (attempts > MAX_ATTEMPTS) {
          setError('Live updates unavailable');
          return;
        }

        setError('SSE connection lost');
        // Exponential backoff: a server that is down stays down for a while,
        // and a fixed 5s retry turns one broken tab into a request flood.
        const delay = Math.min(BASE_DELAY_MS * 2 ** (attempts - 1), MAX_DELAY_MS);
        retryTimer = setTimeout(() => {
          if (mounted) connect();
        }, delay);
      };
    };

    connect();

    return () => {
      mounted = false;
      if (retryTimer) clearTimeout(retryTimer);
      eventSourceRef.current?.close();
    };
  }, []);

  return { newListings, error };
}
