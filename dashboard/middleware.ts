import { NextRequest, NextResponse } from 'next/server';
import { apiRateLimiter } from './lib/rate-limit';

const LIMIT = 30;
const WINDOW_MS = 60_000;
const MAX_IP_LENGTH = 64;

function normalizeIp(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  if (trimmed.length === 0 || trimmed.length > MAX_IP_LENGTH) return null;

  const ipv4Parts = trimmed.split('.');
  if (
    ipv4Parts.length === 4
    && ipv4Parts.every((part) => /^\d{1,3}$/.test(part) && Number(part) <= 255)
  ) {
    return trimmed;
  }

  if (isStrictIpv6(trimmed)) {
    return trimmed;
  }

  return null;
}

function isStrictIpv6(value: string): boolean {
  if (!value.includes(':') || !/^[0-9a-fA-F:]+$/.test(value)) return false;

  const halves = value.split('::');
  if (halves.length > 2) return false;
  if (halves.length === 2) {
    const left = halves[0] === '' ? [] : halves[0].split(':');
    const right = halves[1] === '' ? [] : halves[1].split(':');
    const validGroup = (group: string) => /^[0-9a-fA-F]{1,4}$/.test(group);
    return left.every(validGroup) && right.every(validGroup) && left.length + right.length < 8;
  }

  const groups = value.split(':');
  return groups.length === 8 && groups.every((group) => /^[0-9a-fA-F]{1,4}$/.test(group));
}

/** Trust proxy headers only when deployment overwrites them; invalid/missing identity shares unknown. */
function clientKey(request: NextRequest): string {
  const realIp = normalizeIp(request.headers.get('x-real-ip'));
  if (realIp) return realIp;

  for (const forwardedIp of request.headers.get('x-forwarded-for')?.split(',') ?? []) {
    const normalized = normalizeIp(forwardedIp);
    if (normalized) return normalized;
  }

  return 'unknown';
}

/** Per-process defense in depth; distributed deployments need shared state. */
export function middleware(request: NextRequest) {
  const now = Date.now();
  const result = apiRateLimiter.check(clientKey(request), LIMIT, WINDOW_MS, now);
  const retryAfter = Math.max(1, Math.ceil((result.resetAt - now) / 1_000));
  const response = result.allowed
    ? NextResponse.next()
    : NextResponse.json(
        { error: 'Too many requests. Please try again later.', retryAfter },
        { status: 429 },
      );

  response.headers.set('X-RateLimit-Limit', String(LIMIT));
  response.headers.set('X-RateLimit-Remaining', String(result.remaining));
  response.headers.set('X-RateLimit-Reset', String(Math.ceil(result.resetAt / 1000)));
  if (!result.allowed) response.headers.set('Retry-After', String(retryAfter));
  return response;
}

export const config = {
  matcher: [
    '/api/listings/:path*',
    '/api/insights',
    '/api/district-heatmap',
  ],
};
