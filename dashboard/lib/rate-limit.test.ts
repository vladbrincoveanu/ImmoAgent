import { describe, expect, it, jest } from '@jest/globals';
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

  it('fails closed on rollback after forward cleanup', () => {
    const limiter = new SlidingWindowRateLimiter();
    const clearExpired = jest.spyOn(limiter, 'clearExpired');

    limiter.check('ip', 1, 100, 1_000);
    limiter.clearExpired(1_101);
    clearExpired.mockClear();

    const rollback = limiter.check('ip', 1, 100, 900);

    expect(rollback.allowed).toBe(false);
    expect(rollback.resetAt).toBe(1_201);
    expect(clearExpired).not.toHaveBeenCalled();
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

  it.each([null, undefined, 42, '', '   '])('rejects invalid key %p', (key) => {
    const limiter = new SlidingWindowRateLimiter();

    expect(() => limiter.check(key as string, 1, 1_000, 0)).toThrow(RangeError);
    expect(limiter.size()).toBe(0);
  });

  it.each([-1, Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY])(
    'rejects invalid now %p',
    (now) => {
      const limiter = new SlidingWindowRateLimiter();

      expect(() => limiter.check('ip', 1, 1_000, now)).toThrow(RangeError);
      expect(limiter.size()).toBe(0);
    },
  );

  it.each([Number.MAX_SAFE_INTEGER, Number.MAX_VALUE])('rejects overflowing now %p', (now) => {
    const limiter = new SlidingWindowRateLimiter();

    expect(() => limiter.check('ip', 1, 1_000, now)).toThrow(RangeError);
  });

  it('blocks clock rollback against the global high-water time', () => {
    const limiter = new SlidingWindowRateLimiter();

    expect(limiter.check('rollback', 3, 100, 1_000).allowed).toBe(true);
    const rollback = limiter.check('rollback', 3, 100, 900);

    expect(rollback.allowed).toBe(false);
    expect(rollback.resetAt).toBe(1_100);
  });

  it.each([
    0,
    -1,
    Number.NaN,
    Number.POSITIVE_INFINITY,
    Number.NEGATIVE_INFINITY,
    Number.MAX_SAFE_INTEGER,
    Number.MAX_VALUE,
  ])(
    'rejects invalid windowMs %p',
    (windowMs) => {
      const limiter = new SlidingWindowRateLimiter();
      expect(() => limiter.check('ip', 1, windowMs, 0)).toThrow(RangeError);
    },
  );

  it.each([0, -1, 1.5, Number.NaN, Number.POSITIVE_INFINITY, Number.MAX_SAFE_INTEGER])(
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

  it('rejects maxKeys above the hard cap', () => {
    expect(() => new SlidingWindowRateLimiter(10_001)).toThrow(RangeError);
  });

  it.each([0, -1, 1.5, Number.NaN, Number.POSITIVE_INFINITY])(
    'rejects invalid maxEventsPerKey %p',
    (maxEventsPerKey) => {
      expect(() => new SlidingWindowRateLimiter(10, maxEventsPerKey)).toThrow(RangeError);
    },
  );

  it('rejects maxEventsPerKey above the hard cap', () => {
    expect(() => new SlidingWindowRateLimiter(10, 101)).toThrow(RangeError);
  });

  it('rejects a limit above the default maxEventsPerKey cap', () => {
    const limiter = new SlidingWindowRateLimiter();

    expect(() => limiter.check('ip', 101, 1_000, 0)).toThrow(RangeError);
    expect(limiter.size()).toBe(0);
  });

  it('enforces a configured maxEventsPerKey cap', () => {
    const limiter = new SlidingWindowRateLimiter(10, 2);

    expect(() => limiter.check('ip', 3, 1_000, 0)).toThrow(RangeError);
  });

  it.each([0, -1, 1.5, Number.NaN, Number.POSITIVE_INFINITY])(
    'rejects invalid maxTotalEvents %p',
    (maxTotalEvents) => {
      expect(() => new SlidingWindowRateLimiter(10, 100, maxTotalEvents)).toThrow(RangeError);
    },
  );

  it('rejects maxTotalEvents above the hard cap', () => {
    expect(() => new SlidingWindowRateLimiter(10, 100, 100_001)).toThrow(RangeError);
  });

  it('fails closed without evicting active buckets at total capacity', () => {
    const limiter = new SlidingWindowRateLimiter(10, 100, 1);

    limiter.check('first', 2, 100, 0);
    const blocked = limiter.check('second', 2, 100, 1);

    expect(limiter.size()).toBe(1);
    expect(blocked.allowed).toBe(false);
    expect(blocked.resetAt).toBe(100);
  });

  it('prunes only the requested key during normal checks', () => {
    const limiter = new SlidingWindowRateLimiter(3);

    limiter.check('stale', 1, 100, 0);
    limiter.check('active', 1, 100, 50);
    limiter.check('other', 1, 100, 50);

    limiter.check('active', 1, 100, 201);

    expect(limiter.size()).toBe(3);
    expect(limiter.check('stale', 1, 100, 201).allowed).toBe(true);
  });

  it('evicts expired keys before enforcing capacity', () => {
    const limiter = new SlidingWindowRateLimiter(2);

    limiter.check('expired', 1, 100, 0);
    limiter.check('active', 1, 100, 50);
    limiter.check('new', 1, 100, 101);

    expect(limiter.size()).toBe(2);
    expect(limiter.check('active', 1, 100, 101).allowed).toBe(false);
  });

  it('reaps expired keys on a bounded capacity cleanup cadence', () => {
    const limiter = new SlidingWindowRateLimiter(1);

    limiter.check('active', 1, 100, 0);
    expect(limiter.check('new', 1, 100, 50).allowed).toBe(false);
    expect(limiter.check('new', 1, 100, 101).allowed).toBe(false);
    expect(limiter.check('new', 1, 100, 1_050).allowed).toBe(true);
  });

  it('uses a safe future reset when deferred cleanup leaves no active release', () => {
    const limiter = new SlidingWindowRateLimiter(1);

    limiter.check('active', 1, 100, 0);
    limiter.check('new', 1, 100, 50);
    const blocked = limiter.check('new', 1, 100, 101);

    expect(blocked.allowed).toBe(false);
    expect(blocked.resetAt).toBe(201);
  });

  it('fails closed without evicting active buckets at key capacity', () => {
    const limiter = new SlidingWindowRateLimiter(2);

    limiter.check('first', 1, 100, 0);
    limiter.check('second', 1, 100, 1);
    const blocked = limiter.check('third', 1, 100, 2);

    expect(limiter.size()).toBe(2);
    expect(blocked.allowed).toBe(false);
    expect(blocked.resetAt).toBe(100);
    expect(limiter.check('first', 1, 100, 2).allowed).toBe(false);
  });

  it('reports earliest active release when capacity rejects', () => {
    const limiter = new SlidingWindowRateLimiter(2);

    limiter.check('first', 1, 1_000, 0);
    limiter.check('second', 1, 1_000, 500);

    const blocked = limiter.check('third', 1, 1_000, 501);

    expect(blocked.allowed).toBe(false);
    expect(blocked.resetAt).toBe(1_000);
  });

  it('waits for the last event before releasing a key slot', () => {
    const limiter = new SlidingWindowRateLimiter(1, 2);

    limiter.check('first', 2, 100, 0);
    limiter.check('first', 2, 100, 50);
    const blocked = limiter.check('second', 2, 100, 51);

    expect(blocked.allowed).toBe(false);
    expect(blocked.resetAt).toBe(150);
  });

  it('uses the earliest event release for total-event capacity', () => {
    const limiter = new SlidingWindowRateLimiter(10, 2, 2);

    limiter.check('first', 1, 100, 0);
    limiter.check('second', 1, 100, 50);
    const blocked = limiter.check('third', 1, 100, 51);

    expect(blocked.allowed).toBe(false);
    expect(blocked.resetAt).toBe(100);
  });

  it('returns the later release when key and event capacity both block', () => {
    const limiter = new SlidingWindowRateLimiter(1, 2, 2);

    limiter.check('first', 2, 100, 0);
    limiter.check('first', 2, 100, 50);
    const blocked = limiter.check('second', 2, 100, 51);

    expect(blocked.allowed).toBe(false);
    expect(blocked.resetAt).toBe(150);
  });
});
