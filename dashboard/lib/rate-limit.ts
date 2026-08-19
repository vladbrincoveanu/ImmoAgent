export type RateLimitResult = {
  allowed: boolean;
  remaining: number;
  resetAt: number;
};

const DEFAULT_MAX_KEYS = 10_000;
const DEFAULT_MAX_EVENTS_PER_KEY = 100;
const DEFAULT_MAX_TOTAL_EVENTS = 100_000;
const MAX_WINDOW_MS = 7 * 24 * 60 * 60 * 1_000;
const MAX_SAFE_TIMESTAMP = Number.MAX_SAFE_INTEGER;
const CLEANUP_INTERVAL_MS = 1_000;

type Entry = {
  timestamps: number[];
  windowMs: number;
};

/** Process-local limiter; defaults: 10,000 keys, 100 events/key, 100,000 total events. */
export class SlidingWindowRateLimiter {
  private readonly entries = new Map<string, Entry>();
  private readonly maxKeys: number;
  private readonly maxEventsPerKey: number;
  private readonly maxTotalEvents: number;
  private totalEvents = 0;
  private lastCleanupAt: number | null = null;

  constructor(
    maxKeys = DEFAULT_MAX_KEYS,
    maxEventsPerKey = DEFAULT_MAX_EVENTS_PER_KEY,
    maxTotalEvents = DEFAULT_MAX_TOTAL_EVENTS,
  ) {
    if (!Number.isSafeInteger(maxKeys) || maxKeys <= 0) {
      throw new RangeError('maxKeys must be a positive integer');
    }
    if (!Number.isSafeInteger(maxEventsPerKey) || maxEventsPerKey <= 0) {
      throw new RangeError('maxEventsPerKey must be a positive finite integer');
    }
    if (!Number.isSafeInteger(maxTotalEvents) || maxTotalEvents <= 0) {
      throw new RangeError('maxTotalEvents must be a positive finite integer');
    }
    this.maxKeys = maxKeys;
    this.maxEventsPerKey = maxEventsPerKey;
    this.maxTotalEvents = maxTotalEvents;
  }

  check(key: string, limit: number, windowMs: number, now = Date.now()): RateLimitResult {
    if (typeof key !== 'string' || key.trim() === '') {
      throw new RangeError('key must be a non-empty string');
    }
    if (!Number.isSafeInteger(limit) || limit <= 0) {
      throw new RangeError('limit must be a positive integer');
    }
    if (limit > this.maxEventsPerKey) {
      throw new RangeError(`limit must not exceed ${this.maxEventsPerKey}`);
    }
    if (!Number.isFinite(windowMs) || windowMs <= 0) {
      throw new RangeError('windowMs must be a positive finite number');
    }
    if (windowMs > MAX_WINDOW_MS) {
      throw new RangeError('windowMs exceeds the safe limit');
    }
    if (!Number.isFinite(now) || now < 0) {
      throw new RangeError('now must be a finite non-negative number');
    }
    if (now > MAX_SAFE_TIMESTAMP - windowMs) {
      throw new RangeError('now exceeds the safe timestamp limit');
    }

    const current = this.entries.get(key);
    let effectiveNow = now;
    let activeTimestamps: number[];
    if (current) {
      const latestTimestamp = current.timestamps[current.timestamps.length - 1];
      if (latestTimestamp !== undefined && effectiveNow < latestTimestamp) {
        effectiveNow = latestTimestamp;
      }
      if (effectiveNow > MAX_SAFE_TIMESTAMP - windowMs) {
        throw new RangeError('now exceeds the safe timestamp limit');
      }
      current.windowMs = windowMs;
      this.pruneExpired(current, effectiveNow);
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

    if ((!current && this.entries.size >= this.maxKeys) || this.totalEvents >= this.maxTotalEvents) {
      this.maybeReapExpired(effectiveNow);
      if ((!current && this.entries.size >= this.maxKeys) || this.totalEvents >= this.maxTotalEvents) {
        return {
          allowed: false,
          remaining: 0,
          resetAt: effectiveNow + windowMs,
        };
      }
      activeTimestamps = this.entries.get(key)?.timestamps ?? [];
    }

    activeTimestamps.push(effectiveNow);
    this.entries.set(key, { timestamps: activeTimestamps, windowMs });
    this.totalEvents += 1;

    return {
      allowed: true,
      remaining: limit - activeTimestamps.length,
      resetAt: activeTimestamps[0] + windowMs,
    };
  }

  clearExpired(now = Date.now()): void {
    if (!Number.isFinite(now) || now < 0 || now > MAX_SAFE_TIMESTAMP) {
      throw new RangeError('now must be a finite non-negative number');
    }
    this.lastCleanupAt = now;
    for (const [key, entry] of this.entries) {
      this.pruneExpired(entry, now);
      if (entry.timestamps.length === 0) this.entries.delete(key);
    }
  }

  size(): number {
    return this.entries.size;
  }

  private pruneExpired(entry: Entry, now: number): void {
    let expiredCount = 0;
    while (
      expiredCount < entry.timestamps.length
      && entry.timestamps[expiredCount] + entry.windowMs < now
    ) {
      expiredCount += 1;
    }
    if (expiredCount === 0) return;

    this.totalEvents -= expiredCount;
    entry.timestamps = entry.timestamps.slice(expiredCount);
  }

  private maybeReapExpired(now: number): void {
    if (this.lastCleanupAt !== null && now - this.lastCleanupAt < CLEANUP_INTERVAL_MS) return;
    this.clearExpired(now);
  }
}

export const apiRateLimiter = new SlidingWindowRateLimiter();
