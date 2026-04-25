import { NextRequest, NextResponse } from 'next/server';
import { checkRateLimit } from '@/lib/rate-limiter';

const RATE_LIMIT = 30;
const RATE_LIMIT_WINDOW_MS = 60 * 1000; // 60 seconds
const LISTINGS_PATH_REGEX = /^\/api\/listings\//;

function getClientIp(request: NextRequest): string {
  const forwarded = request.headers.get('x-forwarded-for');
  if (forwarded) {
    return forwarded.split(',')[0].trim();
  }
  return request.ip ?? '127.0.0.1';
}

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Only rate-limit /api/listings/* endpoints
  if (!LISTINGS_PATH_REGEX.test(pathname)) {
    return NextResponse.next();
  }

  const ip = getClientIp(request);
  const result = checkRateLimit(ip, RATE_LIMIT, RATE_LIMIT_WINDOW_MS);

  const response = result.allowed
    ? NextResponse.next()
    : NextResponse.json(
        { error: 'Too many requests. Please try again later.', retryAfter: 60 },
        { status: 429 }
      );

  // Always add rate limit headers
  response.headers.set('X-RateLimit-Limit', String(RATE_LIMIT));
  response.headers.set('X-RateLimit-Remaining', String(result.remaining));
  response.headers.set('X-RateLimit-Reset', String(Math.round(result.resetAt / 1000)));

  if (!result.allowed) {
    response.headers.set('Retry-After', '60');
  }

  return response;
}

export const config = {
  matcher: ['/api/listings/:path*'],
};
