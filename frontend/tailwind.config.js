/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        buy: '#10b981',
        sell: '#ef4444',
        hold: '#f59e0b',
        'dark-bg': '#0d1117',
        'dark-card': '#161b22',
        'dark-border': '#30363d',
      },
    },
  },
  plugins: [],
}
