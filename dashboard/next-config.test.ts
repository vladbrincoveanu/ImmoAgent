import { describe, expect, it } from '@jest/globals';

const nextConfig = require('./next.config') as {
  headers?: () => Promise<Array<{ source: string; headers: Array<{ key: string; value: string }> }>>;
  images: { remotePatterns: Array<{ protocol: string; hostname: string }> };
};

describe('Next.js security configuration', () => {
  it('sets low-risk security headers for every route', async () => {
    const routes = await nextConfig.headers?.();

    expect(routes).toEqual([{
      source: '/(.*)',
      headers: [
        { key: 'X-Content-Type-Options', value: 'nosniff' },
        { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
        { key: 'X-Frame-Options', value: 'DENY' },
        { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
      ],
    }]);
  });

  it('preserves the explicit image host allowlist', () => {
    expect(nextConfig.images.remotePatterns).toEqual([
      { protocol: 'https', hostname: 'img.derstandard.at' },
      { protocol: 'https', hostname: 'static.derstandard.at' },
      { protocol: 'https', hostname: 'cache.derstandard.at' },
      { protocol: 'https', hostname: 'images.willhaben.at' },
      { protocol: 'https', hostname: 'cache.willhaben.at' },
      { protocol: 'https', hostname: 'cdn.willhaben.at' },
      { protocol: 'https', hostname: 'pictures.immokurier.at' },
      { protocol: 'https', hostname: 'cdn.immokurier.at' },
    ]);
  });
});
