import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'Global Market Intelligence — Institutional Research Platform',
  description:
    'Structured, explainable, thesis-driven market intelligence for institutional investors, macro traders, and research desks.',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="bg-[#0d1117] text-gray-100 min-h-screen antialiased">
        {children}
      </body>
    </html>
  )
}
