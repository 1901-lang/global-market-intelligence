/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable standalone output for optimised Docker production builds
  output: process.env.NODE_ENV === 'production' ? 'standalone' : undefined,

  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  },

  // ── HTTP Security Headers ──────────────────────────────────────────────────
  async headers() {
    const isProduction = process.env.NODE_ENV === 'production'
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

    return [
      {
        // Apply to all routes
        source: '/(.*)',
        headers: [
          {
            key: 'X-Content-Type-Options',
            value: 'nosniff',
          },
          {
            key: 'X-Frame-Options',
            value: 'DENY',
          },
          {
            key: 'Referrer-Policy',
            value: 'strict-origin-when-cross-origin',
          },
          {
            key: 'Permissions-Policy',
            value: 'geolocation=(), microphone=(), camera=()',
          },
          // Content-Security-Policy: allow self + the backend API origin.
          // Note: 'unsafe-inline' is required for Next.js styled-jsx; remove it
          // once you migrate to a nonce-based CSP in production.
          // 'unsafe-eval' is intentionally omitted (only needed for dev HMR).
          {
            key: 'Content-Security-Policy',
            value: [
              "default-src 'self'",
              "script-src 'self' 'unsafe-inline'",
              "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
              "font-src 'self' https://fonts.gstatic.com",
              "img-src 'self' data: blob:",
              `connect-src 'self' ${apiUrl}`,
              "frame-ancestors 'none'",
            ].join('; '),
          },
          // HSTS — enforced in production (auren-workspace.com is served over HTTPS)
          ...(isProduction
            ? [{ key: 'Strict-Transport-Security', value: 'max-age=63072000; includeSubDomains; preload' }]
            : []),
        ],
      },
    ]
  },
}

module.exports = nextConfig
