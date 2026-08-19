import { NextRequest, NextResponse } from 'next/server';
import { apiRateLimiter } from './lib/rate-limit';

const LIMIT = 30;
const WINDOW_MS = 60_000;

function clientKey(request: NextRequest): string {
  const realIp = request.headers.get('x-real-ip')?.trim();
  if (realIp) return realIp;

  for (const forwardedIp of request.headers.get('x-forwarded-for')?.split(',') ?? []) {
    const trimmed = forwardedIp.trim();
    if (trimmed) return trimmed;
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
