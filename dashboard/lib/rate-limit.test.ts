import { describe, expect, it } from '@jest/globals';
import { SlidingWindowRateLimiter } from './rate-limit';

describe('SlidingWindowRateLimiter', () => {
  it('allows the configured number of requests and then rejects', () => {
    const limiter = new SlidingWindowRateLimiter();

    expect(limiter.check('ip', 2, 60_000, 1_000).allowed).toBe(true);
    expect(limiter.check('ip', 2, 60_000, 1_001).allowed).toBe(true);

    const blocked = limiter.check('ip', 2, 60_000, 1_002);
    expect(blocked.allowed).toBe(false);
    expect(blocked.remaining).toBe(0);
    expect(blocked.resetAt).toBe(61_000);
  });

  it('resets an expired window and removes expired entries', () => {
    const limiter = new SlidingWindowRateLimiter();

    expect(limiter.check('ip', 1, 1_000, 1_000).allowed).toBe(true);
    expect(limiter.check('ip', 1, 1_000, 2_000).allowed).toBe(true);
    expect(limiter.size()).toBe(1);

    limiter.clearExpired(3_001);
    expect(limiter.size()).toBe(0);
  });
});
