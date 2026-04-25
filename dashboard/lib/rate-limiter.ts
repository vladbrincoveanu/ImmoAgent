/**
 * Sliding window rate limiter using an in-memory Map.
 * NOTE: State resets on Edge function cold starts. For production,
 * replace with Upstash Redis for durable state.
 */

interface RateLimitEntry {
  count: number;
  windowStart: number;
}

const entries = new Map<string, RateLimitEntry>();

export interface RateLimitResult {
  allowed: boolean;
  remaining: number;
  resetAt: number;
}

export function checkRateLimit(
  ip: string,
  limit: number,
  windowMs: number
): RateLimitResult {
  const now = Date.now();
  const entry = entries.get(ip);

  if (!entry || now - entry.windowStart > windowMs) {
    // New window
    entries.set(ip, { count: 1, windowStart: now });
    return {
      allowed: true,
      remaining: limit - 1,
      resetAt: now + windowMs,
    };
  }

  entry.count++;
  entries.set(ip, entry);

  if (entry.count > limit) {
    return {
      allowed: false,
      remaining: 0,
      resetAt: entry.windowStart + windowMs,
    };
  }

  return {
    allowed: true,
    remaining: limit - entry.count,
    resetAt: entry.windowStart + windowMs,
  };
}
