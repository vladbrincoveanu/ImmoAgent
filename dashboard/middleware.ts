import { NextRequest, NextResponse } from 'next/server';
import { apiRateLimiter } from './lib/rate-limit';

/**
 * IP identity is a deployment-boundary contract: Vercel or ingress must overwrite
 * x-vercel-forwarded-for, x-real-ip, and x-forwarded-for before this app sees them.
 * The app cannot authenticate client-supplied IP headers itself; invalid or missing
 * values deliberately share the unknown bucket.
 */
const LIMIT = 30;
const WINDOW_MS = 60_000;
const MAX_IP_LENGTH = 64;

function normalizeIp(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  if (trimmed.length === 0 || trimmed.length > MAX_IP_LENGTH) return null;

  return normalizeIpv4(trimmed) ?? normalizeIpv6(trimmed);
}

function normalizeIpv4(value: string): string | null {
  const parts = value.split('.');
  if (parts.length !== 4 || !parts.every((part) => /^\d{1,3}$/.test(part) && Number(part) <= 255)) {
    return null;
  }
  return parts.map((part) => String(Number(part))).join('.');
}

function expandIpv4Tail(groups: string[]): string[] | null {
  const dottedIndex = groups.findIndex((group) => group.includes('.'));
  if (dottedIndex === -1) return groups;
  if (dottedIndex !== groups.length - 1) return null;

  const normalized = normalizeIpv4(groups[dottedIndex]);
  if (!normalized) return null;
  const octets = normalized.split('.').map(Number);
  return [
    ...groups.slice(0, dottedIndex),
    (octets[0] * 256 + octets[1]).toString(16).padStart(4, '0'),
    (octets[2] * 256 + octets[3]).toString(16).padStart(4, '0'),
  ];
}

function normalizeIpv6(value: string): string | null {
  if (!value.includes(':') || !/^[0-9a-fA-F:.]+$/.test(value)) return null;

  const halves = value.split('::');
  if (halves.length > 2) return null;
  const validGroup = (group: string) => /^[0-9a-fA-F]{1,4}$/.test(group);
  let groups: number[];
  if (halves.length === 2) {
    const left = halves[0] === '' ? [] : halves[0].split(':');
    const rawRight = halves[1] === '' ? [] : halves[1].split(':');
    const right = expandIpv4Tail(rawRight);
    if (!right) return null;
    if (!left.every(validGroup) || !right.every(validGroup) || left.length + right.length >= 8) {
      return null;
    }
    groups = [...left, ...Array(8 - left.length - right.length).fill('0'), ...right]
      .map((group) => Number.parseInt(group, 16));
  } else {
    const uncompressed = expandIpv4Tail(value.split(':'));
    if (!uncompressed) return null;
    if (uncompressed.length !== 8 || !uncompressed.every(validGroup)) return null;
    groups = uncompressed.map((group) => Number.parseInt(group, 16));
  }

  const isIpv4Mapped = groups.slice(0, 5).every((group) => group === 0) && groups[5] === 0xffff;
  if (isIpv4Mapped) {
    const high = groups[6];
    const low = groups[7];
    return [
      Math.floor(high / 256),
      high % 256,
      Math.floor(low / 256),
      low % 256,
    ].join('.');
  }

  let bestStart = -1;
  let bestLength = 0;
  for (let start = 0; start < groups.length;) {
    if (groups[start] !== 0) {
      start += 1;
      continue;
    }
    let end = start;
    while (end < groups.length && groups[end] === 0) end += 1;
    if (end - start > bestLength && end - start >= 2) {
      bestStart = start;
      bestLength = end - start;
    }
    start = end;
  }

  if (bestStart === -1) return groups.map((group) => group.toString(16)).join(':');
  const left = groups.slice(0, bestStart).map((group) => group.toString(16)).join(':');
  const right = groups.slice(bestStart + bestLength).map((group) => group.toString(16)).join(':');
  if (left === '') return `::${right}`;
  if (right === '') return `${left}::`;
  return `${left}::${right}`;
}

/** Select normalized identities in the deployment-defined header order. */
function clientKey(request: NextRequest): string {
  const vercelIp = normalizeIp(request.headers.get('x-vercel-forwarded-for'));
  if (vercelIp) return vercelIp;

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
