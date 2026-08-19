export type RateLimitResult = {
  allowed: boolean;
  remaining: number;
  resetAt: number;
};

const DEFAULT_MAX_KEYS = 10_000;

type Entry = {
  timestamps: number[];
  windowMs: number;
};

/** Process-local limiter with max 10,000 keys by default and FIFO eviction. */
export class SlidingWindowRateLimiter {
  private readonly entries = new Map<string, Entry>();
  private readonly maxKeys: number;

  constructor(maxKeys = DEFAULT_MAX_KEYS) {
    if (!Number.isSafeInteger(maxKeys) || maxKeys <= 0) {
      throw new RangeError('maxKeys must be a positive integer');
    }
    this.maxKeys = maxKeys;
  }

  check(key: string, limit: number, windowMs: number, now = Date.now()): RateLimitResult {
    if (!Number.isSafeInteger(limit) || limit <= 0) {
      throw new RangeError('limit must be a positive integer');
    }
    if (!Number.isFinite(windowMs) || windowMs <= 0) {
      throw new RangeError('windowMs must be a positive finite number');
    }

    const current = this.entries.get(key);
    if (current) current.windowMs = windowMs;
    this.clearExpired(now);
    const timestamps = this.entries.get(key)?.timestamps ?? [];
    const activeTimestamps = timestamps.filter((timestamp) => timestamp + windowMs >= now);

    if (activeTimestamps.length >= limit) {
      return {
        allowed: false,
        remaining: 0,
        resetAt: activeTimestamps[0] + windowMs,
      };
    }

    if (!this.entries.has(key) && this.entries.size >= this.maxKeys) {
      this.evictOldest();
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
      entry.timestamps = entry.timestamps.filter(
        (timestamp) => timestamp + entry.windowMs >= now,
      );
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
}

export const apiRateLimiter = new SlidingWindowRateLimiter();
