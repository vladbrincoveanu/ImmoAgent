import { afterEach, describe, expect, it, jest } from '@jest/globals';
import { NextRequest } from 'next/server';
import { config, middleware } from './middleware';

function makeRequest(ip?: string, forwardedFor?: string, trustedIp?: string): NextRequest {
  const headers = new Headers();
  if (ip !== undefined) headers.set('x-real-ip', ip);
  if (forwardedFor !== undefined) headers.set('x-forwarded-for', forwardedFor);
  const request = new NextRequest('http://localhost/api/insights', { headers });
  if (trustedIp !== undefined) {
    Object.defineProperty(request, 'ip', { configurable: true, value: trustedIp });
  }
  return request;
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

  it('prefers a valid trusted request.ip over changing headers', () => {
    const trustedIp = '2001:db8::1';
    for (let request = 1; request <= 30; request += 1) {
      middleware(makeRequest(`192.0.2.${request}`, undefined, trustedIp));
    }

    expect(middleware(makeRequest('192.0.2.31', undefined, trustedIp)).status).toBe(429);
  });

  it('falls back to unknown for empty, spoofed, and overlong IP headers', () => {
    const invalidIps = ['', 'spoofed.example', '1'.repeat(65)];
    for (const invalidIp of invalidIps) {
      for (let request = 0; request < 10; request += 1) {
        middleware(makeRequest(invalidIp));
      }
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
    const now = jest.spyOn(Date, 'now').mockReturnValue(1_000);
    const ip = '203.0.113.5';
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
