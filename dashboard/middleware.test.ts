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
    const response = middleware(makeRequest('middleware-allowed', 'forwarded-allowed'));

    expect(response.status).toBe(200);
    expect(response.headers.get('X-RateLimit-Limit')).toBe('30');
    expect(response.headers.get('X-RateLimit-Remaining')).toBe('29');
    expect(response.headers.get('X-RateLimit-Reset')).toMatch(/^\d+$/);
    expect(response.headers.get('Retry-After')).toBeNull();
  });

  it('uses forwarded address when x-real-ip is unavailable', () => {
    const realIp = 'middleware-preferred';
    const forwardedIp = 'middleware-forwarded';
    for (let request = 0; request < 30; request += 1) {
      middleware(makeRequest(realIp, forwardedIp));
    }

    expect(middleware(makeRequest(realIp, forwardedIp)).status).toBe(429);
    expect(middleware(makeRequest(undefined, forwardedIp)).status).toBe(200);
  });

  it('trims IP headers and falls back when x-real-ip is empty', () => {
    const forwardedIp = 'fallback-normalized';
    for (let request = 0; request < 30; request += 1) {
      middleware(makeRequest('   ', `  ${forwardedIp}  `));
    }

    expect(middleware(makeRequest(undefined, forwardedIp)).status).toBe(429);
  });

  it('returns JSON 429 with rate headers after the limit', async () => {
    const ip = 'middleware-blocked';
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
    const now = jest.spyOn(Date, 'now').mockReturnValue(1_000);
    const ip = 'middleware-derived-retry';
    for (let request = 0; request < 30; request += 1) {
      expect(middleware(makeRequest(ip)).status).toBe(200);
    }

    now.mockReturnValue(59_500);
    const response = middleware(makeRequest(ip));
    expect(response.headers.get('Retry-After')).toBe('2');
    expect((await response.json()).retryAfter).toBe(2);

    now.mockReturnValue(60_999);
    const minimum = middleware(makeRequest(ip));
    expect(minimum.headers.get('Retry-After')).toBe('1');
    expect((await minimum.json()).retryAfter).toBe(1);
  });
});
