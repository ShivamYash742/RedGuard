// Where /api/* is proxied. Docker sets BACKEND_URL (the backend service);
// everywhere else it is the local uvicorn. Rewrites are resolved at build time.
const backendUrl = (process.env.BACKEND_URL || 'http://localhost:8000').replace(/\/$/, '')

/** @type {import('next').NextConfig} */
const nextConfig = {
  // Only the Docker image builds the standalone server; `npm start` is unchanged.
  output: process.env.NEXT_OUTPUT === 'standalone' ? 'standalone' : undefined,
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`, // Proxy to FastAPI backend
      },
    ]
  },
  // v3 IA consolidated 14 routes into 5 (Overview, Corpus, Runs, Models, Settings).
  // These keep old bookmarks and external links reachable.
  async redirects() {
    return [
      { source: '/benchmark', destination: '/runs', permanent: true },
      { source: '/history', destination: '/runs', permanent: true },
      {
        source: '/reports',
        has: [{ type: 'query', key: 'session', value: '(?<session>.*)' }],
        destination: '/runs/:session',
        permanent: true,
      },
      { source: '/reports', destination: '/runs', permanent: true },
      { source: '/probes', destination: '/corpus', permanent: true },
      { source: '/probes/:probeId', destination: '/corpus/probes/:probeId', permanent: true },
      { source: '/attack-families', destination: '/corpus', permanent: true },
      { source: '/attack-families/:familyId', destination: '/corpus/families/:familyId', permanent: true },
      { source: '/scenarios', destination: '/corpus', permanent: true },
      { source: '/datasets', destination: '/corpus', permanent: true },
      { source: '/comparison', destination: '/models', permanent: true },
      { source: '/policy', destination: '/settings?tab=policy', permanent: true },
      { source: '/audit', destination: '/settings?tab=audit', permanent: true },
    ]
  },
  // Disable response body size limit so SSE streams can flow through the proxy
  // without being truncated or timed out (needed for long-running scan families)
  experimental: {
    proxyTimeout: 300000, // 5 minutes — covers the longest possible scan family
  },
}

module.exports = nextConfig
