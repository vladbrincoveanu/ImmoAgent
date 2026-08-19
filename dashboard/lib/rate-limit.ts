export type RateLimitResult = {
  allowed: boolean;
  remaining: number;
  resetAt: number;
};

type Entry = {
  count: number;
  resetAt: number;
};

export class SlidingWindowRateLimiter {
  private readonly entries = new Map<string, Entry>();

  check(key: string, limit: number, windowMs: number, now = Date.now()): RateLimitResult {
    this.clearExpired(now);
    const current = this.entries.get(key);
    const entry = current && current.resetAt > now
      ? { count: current.count + 1, resetAt: current.resetAt }
      : { count: 1, resetAt: now + windowMs };
    this.entries.set(key, entry);
    const allowed = entry.count <= limit;

    return {
      allowed,
      remaining: allowed ? Math.max(0, limit - entry.count) : 0,
      resetAt: entry.resetAt,
    };
  }

  clearExpired(now = Date.now()): void {
    for (const [key, entry] of this.entries) {
      if (entry.resetAt <= now) this.entries.delete(key);
    }
  }

  size(): number {
    return this.entries.size;
  }
}

export const apiRateLimiter = new SlidingWindowRateLimiter();
