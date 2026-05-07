/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  // /api/v1/* → gateway (microservices auth, purchases, etc.)
  // /api/*    → backend-monolith (legacy endpoints)
  // beforeFiles ensures local Next.js API routes (pages/api/*) take precedence.
  async rewrites() {
    return {
      beforeFiles: [],
      afterFiles: [
        {
          source: '/api/v1/:path*',
          destination: `${process.env.GATEWAY_URL || 'http://gateway:3000'}/api/v1/:path*`,
        },
        {
          source: '/api/:path*',
          destination: `${process.env.BACKEND_MONOLITH_URL || 'http://backend-monolith:4000'}/:path*`,
        },
      ],
      fallback: [],
    };
  },
};

module.exports = nextConfig;
