import Link from 'next/link'

export function Footer() {
  return (
    <footer className="border-t border-slate-800/60 bg-[#050c1a]">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-10 sm:py-12">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
          {/* Brand */}
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded bg-cyan-500/20 border border-cyan-500/40 flex items-center justify-center">
                <span className="text-cyan-400 text-xs font-bold">◈</span>
              </div>
              <span className="text-white font-semibold text-sm">Global Market Intelligence</span>
            </div>
            <p className="text-xs text-slate-600">
              © {new Date().getFullYear()} AIP Platform. All rights reserved.
            </p>
          </div>

          {/* Links */}
          <nav className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm" aria-label="Footer navigation">
            <Link href="/dashboard" className="text-slate-500 hover:text-slate-300 transition-colors">
              Dashboard
            </Link>
            <a
              href="http://localhost:8000/docs"
              target="_blank"
              rel="noopener noreferrer"
              className="text-slate-500 hover:text-slate-300 transition-colors"
            >
              API Docs
            </a>
            <Link href="/login" className="text-slate-500 hover:text-slate-300 transition-colors">
              Sign in
            </Link>
            <Link href="/login?mode=register" className="text-slate-500 hover:text-slate-300 transition-colors">
              Register
            </Link>
            <a href="#" className="text-slate-500 hover:text-slate-300 transition-colors">Privacy</a>
            <a href="#" className="text-slate-500 hover:text-slate-300 transition-colors">Terms</a>
          </nav>
        </div>

        {/* Disclaimer */}
        <div className="mt-8 pt-6 border-t border-slate-800/50">
          <p className="text-xs text-slate-700 leading-relaxed max-w-3xl">
            Global Market Intelligence is a decision-support platform providing structured analysis
            and intelligence outputs. It does not constitute financial advice, investment recommendations,
            or solicitation to buy or sell any financial instrument. All outputs are for informational
            purposes only and intended for sophisticated institutional users.
          </p>
        </div>
      </div>
    </footer>
  )
}
