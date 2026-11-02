/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() { return [{ source: '/api/backend/:path*', destination: 'http://127.0.0.1:8000/api/:path*' }]; },
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'utfs.io',
        port: ''
      },
      {
        protocol: 'https',
        hostname: 'api.slingacademy.com',
        port: ''
      }
    ]
  },
  transpilePackages: ['geist'],
  typescript: {
    ignoreBuildErrors: false,
  },
  eslint: {
    ignoreDuringBuilds: true,
  },
};

module.exports = nextConfig;
