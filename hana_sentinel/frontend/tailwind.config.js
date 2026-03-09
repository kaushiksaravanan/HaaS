/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Serif Design System - Editorial Elegance
        background: '#FAFAF8',
        foreground: '#1A1A1A',
        muted: {
          DEFAULT: '#F5F3F0',
          foreground: '#6B6B6B',
        },
        accent: {
          DEFAULT: '#B8860B',
          secondary: '#D4A84B',
          foreground: '#FFFFFF',
          muted: 'rgba(184, 134, 11, 0.06)',
        },
        border: {
          DEFAULT: '#E8E4DF',
          hover: '#D4CFC8',
        },
        card: {
          DEFAULT: '#FFFFFF',
          foreground: '#1A1A1A',
        },
        input: '#E8E4DF',
        ring: '#B8860B',

        // Semantic colors with warm undertones
        success: {
          50: '#F0FAF5',
          100: '#D1F5E4',
          500: '#10B981',
          600: '#059669',
          700: '#047857',
        },
        warning: {
          50: '#FFFBEB',
          100: '#FEF3C7',
          500: '#D97706',
          600: '#B45309',
        },
        danger: {
          50: '#FEF2F2',
          100: '#FEE2E2',
          500: '#DC2626',
          600: '#B91C1C',
        },
        info: {
          50: '#F0F9FF',
          100: '#E0F2FE',
          500: '#0EA5E9',
          600: '#0284C7',
        },
      },
      fontFamily: {
        serif: ['"Playfair Display"', 'Georgia', 'serif'],
        sans: ['"Source Sans 3"', 'system-ui', 'sans-serif'],
        mono: ['"IBM Plex Mono"', 'monospace'],
      },
      fontSize: {
        'display': ['4.5rem', { lineHeight: '1.1', letterSpacing: '-0.02em' }],
        'headline': ['2.5rem', { lineHeight: '1.2', letterSpacing: '-0.01em' }],
        'title': ['1.5rem', { lineHeight: '1.3' }],
        'body-lg': ['1.125rem', { lineHeight: '1.75', letterSpacing: '0.01em' }],
      },
      boxShadow: {
        'soft': '0 1px 2px rgba(26,26,26,0.04)',
        'medium': '0 4px 12px rgba(26,26,26,0.06)',
        'hard': '0 8px 24px rgba(26,26,26,0.08)',
        'accent': '0 4px 14px rgba(184, 134, 11, 0.15)',
      },
      borderRadius: {
        'md': '6px',
        'lg': '8px',
        'xl': '12px',
        '2xl': '16px',
      },
      spacing: {
        '18': '4.5rem',
        '22': '5.5rem',
      },
      letterSpacing: {
        'tight': '-0.02em',
        'wide': '0.05em',
        'wider': '0.1em',
        'widest': '0.15em',
      },
    },
  },
  plugins: [],
}
