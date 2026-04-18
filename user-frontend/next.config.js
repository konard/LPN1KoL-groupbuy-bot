/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  // Proxy /api/* to backend-monolith (bypasses gateway as required)
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.BACKEND_MONOLITH_URL || 'http://backend-monolith:4000'}/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
