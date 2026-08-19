export type RateLimitResult = {
  allowed: boolean;
  remaining: number;
  resetAt: number;
};

const DEFAULT_MAX_KEYS = 10_000;
const DEFAULT_MAX_EVENTS_PER_KEY = 10_000;

type Entry = {
  timestamps: number[];
  windowMs: number;
};

/** Process-local limiter; maxKeys and maxEventsPerKey default to 10,000 with FIFO eviction. */
export class SlidingWindowRateLimiter {
  private readonly entries = new Map<string, Entry>();
  private readonly maxKeys: number;
  private readonly maxEventsPerKey: number;

  constructor(maxKeys = DEFAULT_MAX_KEYS, maxEventsPerKey = DEFAULT_MAX_EVENTS_PER_KEY) {
    if (!Number.isSafeInteger(maxKeys) || maxKeys <= 0) {
      throw new RangeError('maxKeys must be a positive integer');
    }
    if (!Number.isSafeInteger(maxEventsPerKey) || maxEventsPerKey <= 0) {
      throw new RangeError('maxEventsPerKey must be a positive finite integer');
    }
    this.maxKeys = maxKeys;
    this.maxEventsPerKey = maxEventsPerKey;
  }

  check(key: string, limit: number, windowMs: number, now = Date.now()): RateLimitResult {
    if (!Number.isSafeInteger(limit) || limit <= 0) {
      throw new RangeError('limit must be a positive integer');
    }
    if (limit > this.maxEventsPerKey) {
      throw new RangeError(`limit must not exceed ${this.maxEventsPerKey}`);
    }
    if (!Number.isFinite(windowMs) || windowMs <= 0) {
      throw new RangeError('windowMs must be a positive finite number');
    }

    const current = this.entries.get(key);
    let activeTimestamps: number[];
    if (current) {
      current.windowMs = windowMs;
      this.pruneExpired(current, now);
      activeTimestamps = current.timestamps;
    } else {
      activeTimestamps = [];
    }

    if (activeTimestamps.length >= limit) {
      return {
        allowed: false,
        remaining: 0,
        resetAt: activeTimestamps[0] + windowMs,
      };
    }

    if (!current && this.entries.size >= this.maxKeys) {
      this.clearExpired(now);
      if (this.entries.size >= this.maxKeys) this.evictOldest();
    }

    activeTimestamps.push(now);
    this.entries.set(key, { timestamps: activeTimestamps, windowMs });

    return {
      allowed: true,
      remaining: limit - activeTimestamps.length,
      resetAt: activeTimestamps[0] + windowMs,
    };
  }

  clearExpired(now = Date.now()): void {
    for (const [key, entry] of this.entries) {
      this.pruneExpired(entry, now);
      if (entry.timestamps.length === 0) this.entries.delete(key);
    }
  }

  size(): number {
    return this.entries.size;
  }

  private evictOldest(): void {
    const oldest = this.entries.keys().next();
    if (!oldest.done) this.entries.delete(oldest.value);
  }

  private pruneExpired(entry: Entry, now: number): void {
    while (entry.timestamps.length > 0 && entry.timestamps[0] + entry.windowMs < now) {
      entry.timestamps.shift();
    }
  }
}

export const apiRateLimiter = new SlidingWindowRateLimiter();
