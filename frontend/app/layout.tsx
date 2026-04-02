import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'AIP — Market Intelligence Platform',
  description: 'Agentic Multi-Model Market Intelligence Platform',
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
