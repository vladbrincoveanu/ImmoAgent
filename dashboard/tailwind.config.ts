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
      },
      colors: {
        accent: '#E07A5F',
        heading: '#3D405B',
        muted: '#8B8B8B',
        border: '#E8E4E0',
        success: '#81B29A',
        'warm-bg': '#F9F7F4',
        dark: {
          accent: '#E07A5F',
          heading: '#F9F7F4',
          muted: '#A0A0A0',
          border: '#3D3D3D',
          success: '#81B29A',
          'warm-bg': '#1A1A1A',
        },
      },
    },
  },
  plugins: [],
};

export default config;
