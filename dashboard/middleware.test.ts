import { afterEach, describe, expect, it, jest } from '@jest/globals';
import { NextRequest } from 'next/server';
import { config, middleware } from './middleware';

function makeRequest(ip?: string, forwardedFor?: string): NextRequest {
  const headers = new Headers();
  if (ip !== undefined) headers.set('x-real-ip', ip);
  if (forwardedFor !== undefined) headers.set('x-forwarded-for', forwardedFor);
  return new NextRequest('http://localhost/api/insights', { headers });
}

describe('dashboard middleware', () => {
  afterEach(() => {
    jest.restoreAllMocks();
  });

  it('matches only approved public read routes', () => {
    expect(config.matcher).toEqual([
      '/api/listings/:path*',
      '/api/insights',
      '/api/district-heatmap',
    ]);
  });

  it('adds rate headers to allowed responses and prefers x-real-ip', () => {
    const response = middleware(makeRequest('192.0.2.10', '192.0.2.11'));

    expect(response.status).toBe(200);
    expect(response.headers.get('X-RateLimit-Limit')).toBe('30');
    expect(response.headers.get('X-RateLimit-Remaining')).toBe('29');
    expect(response.headers.get('X-RateLimit-Reset')).toMatch(/^\d+$/);
    expect(response.headers.get('Retry-After')).toBeNull();
  });

  it('prefers valid x-real-ip over changing forwarded values', () => {
    const realIp = '192.0.2.30';
    for (let request = 1; request <= 30; request += 1) {
      middleware(makeRequest(realIp, `192.0.2.${request}`));
    }

    expect(middleware(makeRequest(realIp, '192.0.2.31')).status).toBe(429);
  });

  it('shares a limiter bucket across equivalent IPv4 forms', () => {
    const nonCanonicalIp = '192.0.2.01';
    for (let request = 0; request < 30; request += 1) {
      middleware(makeRequest(nonCanonicalIp));
    }

    expect(middleware(makeRequest('192.0.2.1')).status).toBe(429);
  });

  it('shares a limiter bucket across equivalent IPv6 forms', () => {
    const fullIp = '2001:0DB8:0000:0000:0000:0000:0000:0001';
    for (let request = 0; request < 30; request += 1) {
      middleware(makeRequest(fullIp));
    }

    expect(middleware(makeRequest('2001:db8::1')).status).toBe(429);
  });

  it('shares a limiter bucket across embedded IPv4 and hexadecimal IPv6 forms', () => {
    const embeddedIp = '::ffff:192.0.2.77';
    for (let request = 0; request < 30; request += 1) {
      expect(middleware(makeRequest(embeddedIp)).status).toBe(200);
    }

    expect(middleware(makeRequest('::ffff:c000:024d')).status).toBe(429);
  });

  it('uses forwarded address when x-real-ip is unavailable', () => {
    const realIp = '192.0.2.20';
    const forwardedIp = '192.0.2.21';
    for (let request = 0; request < 30; request += 1) {
      middleware(makeRequest(realIp, forwardedIp));
    }

    expect(middleware(makeRequest(realIp, forwardedIp)).status).toBe(429);
    expect(middleware(makeRequest(undefined, forwardedIp)).status).toBe(200);
  });

  it('trims IP headers and falls back when x-real-ip is empty', () => {
    const forwardedIp = '198.51.100.1';
    for (let request = 0; request < 30; request += 1) {
      middleware(makeRequest('   ', `  ${forwardedIp}  `));
    }

    expect(middleware(makeRequest(undefined, forwardedIp)).status).toBe(429);
  });

  it('falls back to unknown for empty, spoofed, and overlong IP headers', () => {
    const invalidIps = ['', 'spoofed.example', '999.1.1.1', '2001:db8:::1', '1'.repeat(65)];
    for (const invalidIp of invalidIps) {
      for (let request = 0; request < 10; request += 1) {
        middleware(makeRequest(invalidIp));
      }
    }

    expect(middleware(makeRequest()).status).toBe(429);
  });

  it('falls back to unknown for malformed IPv6 headers', () => {
    for (let request = 0; request < 30; request += 1) {
      middleware(makeRequest('2001:db8:::1'));
    }

    expect(middleware(makeRequest()).status).toBe(429);
  });

  it('returns JSON 429 with rate headers after the limit', async () => {
    const ip = '203.0.113.2';
    for (let request = 0; request < 30; request += 1) {
      expect(middleware(makeRequest(ip)).status).toBe(200);
    }

    const response = middleware(makeRequest(ip));

    expect(response.status).toBe(429);
    expect(await response.json()).toEqual({
      error: 'Too many requests. Please try again later.',
      retryAfter: 60,
    });
    expect(response.headers.get('X-RateLimit-Limit')).toBe('30');
    expect(response.headers.get('X-RateLimit-Remaining')).toBe('0');
    expect(response.headers.get('X-RateLimit-Reset')).toMatch(/^\d+$/);
    expect(response.headers.get('Retry-After')).toBe('60');
  });

  it('derives retry metadata from the sliding-window reset time', async () => {
    const baseNow = Date.now() + 1_000_000;
    const now = jest.spyOn(Date, 'now').mockReturnValue(baseNow);
    const ip = '203.0.113.5';
    for (let request = 0; request < 30; request += 1) {
      expect(middleware(makeRequest(ip)).status).toBe(200);
    }

    now.mockReturnValue(baseNow + 58_500);
    const response = middleware(makeRequest(ip));
    expect(response.headers.get('Retry-After')).toBe('2');
    expect((await response.json()).retryAfter).toBe(2);

    now.mockReturnValue(baseNow + 59_999);
    const minimum = middleware(makeRequest(ip));
    expect(minimum.headers.get('Retry-After')).toBe('1');
    expect((await minimum.json()).retryAfter).toBe(1);
  });
});
