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
  images: {
    remotePatterns: ALLOWED_IMAGE_HOSTS.map((hostname) => ({
      protocol: 'https',
      hostname,
    })),
  },
};

module.exports = nextConfig;
