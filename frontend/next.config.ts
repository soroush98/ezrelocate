import type { NextConfig } from "next";

const config: NextConfig = {
  // Allow HMR / dev resources when the app is opened via 127.0.0.1 in
  // addition to localhost. Dev-only; ignored in production builds.
  allowedDevOrigins: ["127.0.0.1", "localhost"],
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${process.env.BACKEND_URL ?? "http://localhost:8000"}/api/:path*`,
      },
    ];
  },
};

export default config;
