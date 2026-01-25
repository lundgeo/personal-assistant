import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // Enable static export for S3 deployment
  output: 'export',

  // Disable image optimization for static export
  images: {
    unoptimized: true,
  },

  // Set base path if needed (empty for root)
  basePath: '',

  // Trailing slashes for S3 compatibility
  trailingSlash: true,
};

export default nextConfig;
