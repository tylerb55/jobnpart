import type { NextConfig } from "next";

/** @type {import('next').NextConfig} */
const nextConfig: NextConfig = {
  // other configurations...
  images: {
    domains: [
        'img.parts-catalogs.com',
        // 'another-domain.com' // Add other domains here
    ],
  },
  // other configurations...
};

module.exports = nextConfig;

export default nextConfig;
