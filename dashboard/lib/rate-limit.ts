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
  private highestObservedNow: number | null = null;

  constructor(
    maxKeys = DEFAULT_MAX_KEYS,
    maxEventsPerKey = DEFAULT_MAX_EVENTS_PER_KEY,
    maxTotalEvents = DEFAULT_MAX_TOTAL_EVENTS,
  ) {
    if (!Number.isSafeInteger(maxKeys) || maxKeys <= 0 || maxKeys > DEFAULT_MAX_KEYS) {
      throw new RangeError(`maxKeys must be an integer from 1 to ${DEFAULT_MAX_KEYS}`);
    }
    if (
      !Number.isSafeInteger(maxEventsPerKey)
      || maxEventsPerKey <= 0
      || maxEventsPerKey > DEFAULT_MAX_EVENTS_PER_KEY
    ) {
      throw new RangeError(`maxEventsPerKey must be an integer from 1 to ${DEFAULT_MAX_EVENTS_PER_KEY}`);
    }
    if (
      !Number.isSafeInteger(maxTotalEvents)
      || maxTotalEvents <= 0
      || maxTotalEvents > DEFAULT_MAX_TOTAL_EVENTS
    ) {
      throw new RangeError(`maxTotalEvents must be an integer from 1 to ${DEFAULT_MAX_TOTAL_EVENTS}`);
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
    if (this.highestObservedNow !== null && now < this.highestObservedNow) {
      return {
        allowed: false,
        remaining: 0,
        resetAt: this.highestObservedNow + windowMs,
      };
    }
    this.highestObservedNow = now;

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
      const keyCapacityFull = !this.entries.has(key) && this.entries.size >= this.maxKeys;
      const totalCapacityFull = this.totalEvents >= this.maxTotalEvents;
      if (keyCapacityFull || totalCapacityFull) {
        return {
          allowed: false,
          remaining: 0,
          resetAt: Math.max(
            keyCapacityFull
              ? this.keyCapacityReleaseAt(effectiveNow, windowMs)
              : effectiveNow,
            totalCapacityFull
              ? this.earliestReleaseAt(effectiveNow, windowMs)
              : effectiveNow,
          ),
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
    if (this.highestObservedNow !== null && now < this.highestObservedNow) return;
    this.highestObservedNow = now;
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

  private earliestReleaseAt(fallbackNow: number, fallbackWindowMs: number): number {
    let earliest = Number.POSITIVE_INFINITY;
    for (const entry of this.entries.values()) {
      for (const timestamp of entry.timestamps) {
        const releaseAt = timestamp + entry.windowMs;
        if (releaseAt >= fallbackNow && releaseAt < earliest) earliest = releaseAt;
      }
    }
    return earliest === Number.POSITIVE_INFINITY ? fallbackNow + fallbackWindowMs : earliest;
  }

  private keyCapacityReleaseAt(fallbackNow: number, fallbackWindowMs: number): number {
    let earliest = Number.POSITIVE_INFINITY;
    for (const entry of this.entries.values()) {
      const lastTimestamp = entry.timestamps[entry.timestamps.length - 1];
      if (lastTimestamp === undefined) continue;
      const releaseAt = lastTimestamp + entry.windowMs;
      if (releaseAt >= fallbackNow && releaseAt < earliest) earliest = releaseAt;
    }
    return earliest === Number.POSITIVE_INFINITY ? fallbackNow + fallbackWindowMs : earliest;
  }
}

export const apiRateLimiter = new SlidingWindowRateLimiter();
