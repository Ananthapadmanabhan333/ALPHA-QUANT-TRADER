/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        alpha: {
          bg: '#0A0A0C',
          card: '#121216',
          cardHover: '#181820',
          border: '#22232B',
          borderSubtle: '#1C1D24',
          gold: {
            light: '#F5E6B8',
            DEFAULT: '#D4AF37',
            dark: '#9A7A1C',
            dim: 'rgba(212, 175, 55, 0.15)',
          },
          text: {
            primary: '#F3F4F6',
            secondary: '#9CA3AF',
            muted: '#6B7280',
          },
          status: {
            green: '#10B981',
            red: '#EF4444',
            amber: '#F59E0B',
          }
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['JetBrains Mono', 'Fira Code', 'monospace'],
      },
    },
  },
  plugins: [],
}
