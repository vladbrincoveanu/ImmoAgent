import type { Config } from 'tailwindcss';

const config: Config = {
  darkMode: 'class',
  content: [
    './app/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      fontFamily: {
        'dm-sans': ['DM Sans', 'sans-serif'],
        sans: ['Instrument Sans', 'Inter', '-apple-system', 'sans-serif'],
        display: ['Fraunces', 'Georgia', 'serif'],
      },
      colors: {
        // New /dashboard/map tokens (cool palette)
        ink: '#16243a',
        'ink-2': '#5b6b80',
        'ink-3': '#93a1b3',
        line: '#e6eaf0',
        bg: '#f7f8fa',
        card: '#ffffff',
        accent: '#2456e6',
        'accent-soft': '#eef2fe',
        good: '#0f8a5f',
        'good-soft': '#e8f5ef',
        'mid-ink': '#b06c0a',
        'mid-soft': '#fdf3e4',
        // Legacy warm tokens — kept for /dashboard + /dashboard/taken
        heading: '#3D405B',
        muted: '#8B8B8B',
        border: '#E8E4E0',
        success: '#81B29A',
        'warm-bg': '#F9F7F4',
        dark: {
          heading: '#F9F7F4',
          muted: '#A0A0A0',
          border: '#3D3D3D',
        },
      },
    },
  },
  plugins: [],
};

export default config;
