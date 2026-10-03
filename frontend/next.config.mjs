import { PHASE_DEVELOPMENT_SERVER } from "next/constants.js";

/**
 * 本番：静的エクスポート（Azure Static Web Apps で配信）。/api は SWA のリンクバックエンドで
 *       App Service へ転送し、フロントと API を同一オリジンにする。
 * 開発：next dev の rewrites で /api を FastAPI（localhost:8000）へ転送する。
 */
export default function config(phase) {
  const base = { reactStrictMode: true, poweredByHeader: false, images: { unoptimized: true } };
  if (phase === PHASE_DEVELOPMENT_SERVER) {
    const api = process.env.API_PROXY_TARGET ?? "http://localhost:8000";
    return { ...base, async rewrites() { return [{ source: "/api/:path*", destination: `${api}/api/:path*` }]; } };
  }
  return { ...base, output: "export", trailingSlash: true };
}
