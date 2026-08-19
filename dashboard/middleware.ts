import { NextRequest, NextResponse } from 'next/server';
import { apiRateLimiter } from './lib/rate-limit';

const LIMIT = 30;
const WINDOW_MS = 60_000;

function clientKey(request: NextRequest): string {
  return request.headers.get('x-real-ip')
    ?? request.headers.get('x-forwarded-for')?.split(',')[0]?.trim()
    ?? 'unknown';
}

/** Per-process defense in depth; distributed deployments need shared state. */
export function middleware(request: NextRequest) {
  const result = apiRateLimiter.check(clientKey(request), LIMIT, WINDOW_MS);
  const response = result.allowed
    ? NextResponse.next()
    : NextResponse.json(
        { error: 'Too many requests. Please try again later.', retryAfter: 60 },
        { status: 429 },
      );

  response.headers.set('X-RateLimit-Limit', String(LIMIT));
  response.headers.set('X-RateLimit-Remaining', String(result.remaining));
  response.headers.set('X-RateLimit-Reset', String(Math.ceil(result.resetAt / 1000)));
  if (!result.allowed) response.headers.set('Retry-After', '60');
  return response;
}

export const config = {
  matcher: [
    '/api/listings/:path*',
    '/api/insights',
    '/api/district-heatmap',
  ],
};
