/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  // Proxy /api/* to backend-monolith, except local Next.js API routes.
  // Using beforeFiles so filesystem API routes (pages/api/*) are NOT
  // overridden; the rewrite only fires for paths that have no matching file.
  async rewrites() {
    return {
      beforeFiles: [],
      afterFiles: [
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
