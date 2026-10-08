import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/eval/:path*",
        destination: `${process.env.API_URL}/api/eval/:path*`,
      },
    ];
  },
};

export default nextConfig;
