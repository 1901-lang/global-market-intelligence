/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable standalone output for optimised Docker production builds
  output: process.env.NODE_ENV === 'production' ? 'standalone' : undefined,

  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
  },

  // ── HTTP Security Headers ──────────────────────────────────────────────────
  async headers() {
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
          // Extend 'connect-src' with your production API domain before deploying.
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
              `connect-src 'self' ${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}`,
              "frame-ancestors 'none'",
            ].join('; '),
          },
          // HSTS — uncomment when serving over HTTPS in production
          // { key: 'Strict-Transport-Security', value: 'max-age=63072000; includeSubDomains; preload' },
        ],
      },
    ]
  },
}

module.exports = nextConfig
