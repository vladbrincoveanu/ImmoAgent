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
    expect(limiter.check('ip', 1, 1_000, 2_001).allowed).toBe(true);
    expect(limiter.size()).toBe(1);

    limiter.clearExpired(3_002);
    expect(limiter.size()).toBe(0);
  });

  it('keeps the oldest request at the window boundary', () => {
    const limiter = new SlidingWindowRateLimiter();

    expect(limiter.check('ip', 2, 1_000, 0).allowed).toBe(true);
    expect(limiter.check('ip', 2, 1_000, 900).allowed).toBe(true);

    const blocked = limiter.check('ip', 2, 1_000, 1_000);
    expect(blocked.allowed).toBe(false);
    expect(blocked.remaining).toBe(0);
    expect(blocked.resetAt).toBe(1_000);
  });

  it.each([0, -1, Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY])(
    'rejects invalid windowMs %p',
    (windowMs) => {
      const limiter = new SlidingWindowRateLimiter();
      expect(() => limiter.check('ip', 1, windowMs, 0)).toThrow(RangeError);
    },
  );

  it.each([0, -1, 1.5, Number.NaN, Number.POSITIVE_INFINITY])(
    'rejects invalid limit %p',
    (limit) => {
      const limiter = new SlidingWindowRateLimiter();
      expect(() => limiter.check('ip', limit, 1_000, 0)).toThrow(RangeError);
    },
  );

  it.each([0, -1, 1.5, Number.NaN, Number.POSITIVE_INFINITY])(
    'rejects invalid maxKeys %p',
    (maxKeys) => {
      expect(() => new SlidingWindowRateLimiter(maxKeys)).toThrow(RangeError);
    },
  );

  it('evicts expired keys before enforcing capacity', () => {
    const limiter = new SlidingWindowRateLimiter(2);

    limiter.check('expired', 1, 100, 0);
    limiter.check('active', 1, 100, 50);
    limiter.check('new', 1, 100, 101);

    expect(limiter.size()).toBe(2);
    expect(limiter.check('active', 1, 100, 101).allowed).toBe(false);
  });

  it('evicts the oldest key when capacity remains full', () => {
    const limiter = new SlidingWindowRateLimiter(2);

    limiter.check('first', 1, 100, 0);
    limiter.check('second', 1, 100, 1);
    limiter.check('third', 1, 100, 2);

    expect(limiter.size()).toBe(2);
    expect(limiter.check('first', 1, 100, 2).allowed).toBe(true);
    expect(limiter.check('third', 1, 100, 2).allowed).toBe(false);
  });
});
