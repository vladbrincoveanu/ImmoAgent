export type RateLimitResult = {
  allowed: boolean;
  remaining: number;
  resetAt: number;
};

const DEFAULT_MAX_KEYS = 10_000;
const DEFAULT_MAX_EVENTS_PER_KEY = 100;
const DEFAULT_MAX_TOTAL_EVENTS = 100_000;

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
    if (!Number.isFinite(now) || now < 0) {
      throw new RangeError('now must be a finite non-negative number');
    }

    const current = this.entries.get(key);
    let effectiveNow = now;
    let activeTimestamps: number[];
    if (current) {
      const latestTimestamp = current.timestamps[current.timestamps.length - 1];
      if (latestTimestamp !== undefined && effectiveNow < latestTimestamp) {
        effectiveNow = latestTimestamp;
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
      while (
        this.entries.size > 0
        && (this.entries.size >= this.maxKeys || this.totalEvents >= this.maxTotalEvents)
      ) {
        this.evictOldest();
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
    if (!Number.isFinite(now) || now < 0) {
      throw new RangeError('now must be a finite non-negative number');
    }
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
    if (!oldest.done) {
      const entry = this.entries.get(oldest.value);
      if (entry) this.totalEvents -= entry.timestamps.length;
      this.entries.delete(oldest.value);
    }
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
}

export const apiRateLimiter = new SlidingWindowRateLimiter();
