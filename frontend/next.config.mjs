const nextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  images: { unoptimized: true },

  async rewrites() {
    const api = process.env.API_PROXY_TARGET ?? "http://localhost:8000";

    return [
      {
        source: "/api/:path*",
        destination: `${api}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
