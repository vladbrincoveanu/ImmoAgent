/** @type {import('next').NextConfig} */
const ALLOWED_IMAGE_HOSTS = [
  'img.derstandard.at',
  'static.derstandard.at',
  'cache.derstandard.at',
  'images.willhaben.at',
  'cache.willhaben.at',
  'cdn.willhaben.at',
  'pictures.immokurier.at',
  'cdn.immokurier.at',
];

const nextConfig = {
  headers: async () => [{
    source: '/(.*)',
    headers: [
      { key: 'X-Content-Type-Options', value: 'nosniff' },
      { key: 'Referrer-Policy', value: 'strict-origin-when-cross-origin' },
      { key: 'X-Frame-Options', value: 'DENY' },
      { key: 'Permissions-Policy', value: 'camera=(), microphone=(), geolocation=()' },
    ],
  }],
  images: {
    remotePatterns: ALLOWED_IMAGE_HOSTS.map((hostname) => ({
      protocol: 'https',
      hostname,
    })),
  },
};

module.exports = nextConfig;
