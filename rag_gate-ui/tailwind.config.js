/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        glass: {
          light: 'rgba(255, 255, 255, 0.08)',
          mid: 'rgba(255, 255, 255, 0.12)',
          heavy: 'rgba(255, 255, 255, 0.16)',
          border: 'rgba(255, 255, 255, 0.06)',
        },
        surface: {
          DEFAULT: '#0a0a0f',
          card: '#12121a',
          elevated: '#1a1a26',
        },
        accent: {
          blue: '#5e9eff',
          purple: '#a78bfa',
          cyan: '#22d3ee',
          green: '#34d399',
          amber: '#fbbf24',
          rose: '#fb7185',
        },
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', '"SF Pro Display"', '"Segoe UI"', 'Roboto', 'sans-serif'],
      },
      backdropBlur: {
        xl: '24px',
        '2xl': '40px',
      },
      boxShadow: {
        glass: '0 8px 32px rgba(0, 0, 0, 0.4)',
        'glass-sm': '0 4px 16px rgba(0, 0, 0, 0.3)',
      },
    },
  },
  plugins: [],
}