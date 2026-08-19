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

function safeTimestampAdd(timestamp: number, duration: number): number {
  return timestamp > MAX_SAFE_TIMESTAMP - duration
    ? MAX_SAFE_TIMESTAMP
    : timestamp + duration;
}

type Entry = {
  key: string;
  events: Event[];
  keyReleaseAt: number;
  keyReleaseVersion: number;
};

type Event = {
  timestamp: number;
  expiresAt: number;
  active: boolean;
  entry: Entry;
};

type KeyRelease = {
  entry: Entry;
  releaseAt: number;
  version: number;
};

class MinHeap<T> {
  private readonly values: T[] = [];

  constructor(private readonly compare: (left: T, right: T) => number) {}

  peek(): T | undefined {
    return this.values[0];
  }

  push(value: T): void {
    this.values.push(value);
    let index = this.values.length - 1;
    while (index > 0) {
      const parent = Math.floor((index - 1) / 2);
      if (this.compare(this.values[index], this.values[parent]) >= 0) break;
      [this.values[index], this.values[parent]] = [this.values[parent], this.values[index]];
      index = parent;
    }
  }

  pop(): T | undefined {
    if (this.values.length === 0) return undefined;
    const first = this.values[0];
    const last = this.values.pop();
    if (this.values.length > 0 && last !== undefined) {
      this.values[0] = last;
      let index = 0;
      while (true) {
        const left = index * 2 + 1;
        const right = left + 1;
        let smallest = index;
        if (left < this.values.length && this.compare(this.values[left], this.values[smallest]) < 0) {
          smallest = left;
        }
        if (right < this.values.length && this.compare(this.values[right], this.values[smallest]) < 0) {
          smallest = right;
        }
        if (smallest === index) break;
        [this.values[index], this.values[smallest]] = [this.values[smallest], this.values[index]];
        index = smallest;
      }
    }
    return first;
  }

  clear(): void {
    this.values.length = 0;
  }
}

/** Process-local limiter; defaults: 10,000 keys, 100 events/key, 100,000 total events. */
export class SlidingWindowRateLimiter {
  private readonly entries = new Map<string, Entry>();
  private readonly maxKeys: number;
  private readonly maxEventsPerKey: number;
  private readonly maxTotalEvents: number;
  private totalEvents = 0;
  private lastCleanupAt: number | null = null;
  private highestObservedNow: number | null = null;
  private readonly eventExpiryHeap = new MinHeap<Event>((left, right) => left.expiresAt - right.expiresAt);
  private readonly keyReleaseHeap = new MinHeap<KeyRelease>((left, right) => left.releaseAt - right.releaseAt);

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
        resetAt: safeTimestampAdd(this.highestObservedNow, windowMs),
      };
    }
    this.highestObservedNow = now;

    let entry = this.entries.get(key);
    let effectiveNow = now;
    if (entry) {
      const latestTimestamp = entry.events[entry.events.length - 1]?.timestamp;
      if (latestTimestamp !== undefined && effectiveNow < latestTimestamp) {
        effectiveNow = latestTimestamp;
      }
      if (effectiveNow > MAX_SAFE_TIMESTAMP - windowMs) {
        throw new RangeError('now exceeds the safe timestamp limit');
      }
      this.pruneExpired(entry, effectiveNow);
    }

    if (entry && entry.events.length >= limit) {
      return {
        allowed: false,
        remaining: 0,
        resetAt: this.earliestEntryReleaseAt(entry, effectiveNow, windowMs),
      };
    }

    if ((!entry && this.entries.size >= this.maxKeys) || this.totalEvents >= this.maxTotalEvents) {
      this.maybeReapExpired(effectiveNow);
      entry = this.entries.get(key);
      const keyCapacityFull = !entry && this.entries.size >= this.maxKeys;
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
    }

    if (!entry) {
      entry = {
        key,
        events: [],
        keyReleaseAt: 0,
        keyReleaseVersion: 0,
      };
      this.entries.set(key, entry);
    }

    const event: Event = {
      timestamp: effectiveNow,
      expiresAt: safeTimestampAdd(effectiveNow, windowMs),
      active: true,
      entry,
    };
    entry.events.push(event);
    entry.keyReleaseAt = Math.max(entry.keyReleaseAt, event.expiresAt);
    entry.keyReleaseVersion += 1;
    this.keyReleaseHeap.push({
      entry,
      releaseAt: entry.keyReleaseAt,
      version: entry.keyReleaseVersion,
    });
    this.eventExpiryHeap.push(event);
    this.totalEvents += 1;

    return {
      allowed: true,
      remaining: limit - entry.events.length,
      resetAt: this.earliestEntryReleaseAt(entry, effectiveNow, windowMs),
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
      if (entry.events.length === 0) this.entries.delete(key);
    }
  }

  clear(): void {
    this.entries.clear();
    this.totalEvents = 0;
    this.lastCleanupAt = null;
    this.highestObservedNow = null;
    this.eventExpiryHeap.clear();
    this.keyReleaseHeap.clear();
  }

  size(): number {
    return this.entries.size;
  }

  private pruneExpired(entry: Entry, now: number): void {
    if (entry.events.length === 0) return;

    const activeEvents: Event[] = [];
    for (const event of entry.events) {
      if (event.expiresAt <= now) {
        event.active = false;
        this.totalEvents -= 1;
      } else {
        activeEvents.push(event);
      }
    }
    entry.events = activeEvents;
    if (entry.events.length === 0) {
      entry.keyReleaseAt = 0;
      entry.keyReleaseVersion += 1;
    }
  }

  private maybeReapExpired(now: number): void {
    this.reapExpiredFromHeaps(now);
    if (this.lastCleanupAt !== null && now - this.lastCleanupAt < CLEANUP_INTERVAL_MS) return;
    this.clearExpired(now);
  }

  private reapExpiredFromHeaps(now: number): void {
    while (true) {
      const event = this.eventExpiryHeap.peek();
      if (!event || event.expiresAt > now) break;
      this.eventExpiryHeap.pop();
      if (!event.active) continue;

      event.active = false;
      const entry = event.entry;
      if (this.entries.get(entry.key) !== entry) continue;
      const index = entry.events.indexOf(event);
      if (index === -1) continue;
      entry.events.splice(index, 1);
      this.totalEvents -= 1;
      if (entry.events.length === 0) {
        entry.keyReleaseAt = 0;
        entry.keyReleaseVersion += 1;
        this.entries.delete(entry.key);
      }
    }

    while (true) {
      const release = this.keyReleaseHeap.peek();
      if (!release) break;
      const entry = release.entry;
      const current = this.entries.get(entry.key);
      if (
        current !== entry
        || entry.keyReleaseVersion !== release.version
        || entry.events.length === 0
      ) {
        this.keyReleaseHeap.pop();
        continue;
      }
      if (release.releaseAt > now) break;
      this.keyReleaseHeap.pop();
      this.pruneExpired(entry, now);
      if (entry.events.length === 0) {
        this.entries.delete(entry.key);
      } else {
        entry.keyReleaseAt = Math.max(...entry.events.map((event) => event.expiresAt));
        entry.keyReleaseVersion += 1;
        this.keyReleaseHeap.push({
          entry,
          releaseAt: entry.keyReleaseAt,
          version: entry.keyReleaseVersion,
        });
      }
    }
  }

  private earliestEntryReleaseAt(
    entry: Entry,
    fallbackNow: number,
    fallbackWindowMs: number,
  ): number {
    let earliest = Number.POSITIVE_INFINITY;
    for (const event of entry.events) {
      if (event.expiresAt >= fallbackNow && event.expiresAt < earliest) {
        earliest = event.expiresAt;
      }
    }
    return earliest === Number.POSITIVE_INFINITY
      ? safeTimestampAdd(fallbackNow, fallbackWindowMs)
      : earliest;
  }

  private earliestReleaseAt(fallbackNow: number, fallbackWindowMs: number): number {
    while (true) {
      const event = this.eventExpiryHeap.peek();
      if (!event || event.active) break;
      this.eventExpiryHeap.pop();
    }
    const nextEvent = this.eventExpiryHeap.peek();
    return nextEvent && nextEvent.expiresAt > fallbackNow
      ? nextEvent.expiresAt
      : safeTimestampAdd(fallbackNow, fallbackWindowMs);
  }

  private keyCapacityReleaseAt(fallbackNow: number, fallbackWindowMs: number): number {
    while (true) {
      const release = this.keyReleaseHeap.peek();
      if (!release) break;
      const entry = release.entry;
      if (
        this.entries.get(entry.key) !== entry
        || entry.keyReleaseVersion !== release.version
        || entry.events.length === 0
      ) {
        this.keyReleaseHeap.pop();
        continue;
      }
      if (release.releaseAt > fallbackNow) return release.releaseAt;
      this.keyReleaseHeap.pop();
    }
    return safeTimestampAdd(fallbackNow, fallbackWindowMs);
  }
}

export const apiRateLimiter = new SlidingWindowRateLimiter();
