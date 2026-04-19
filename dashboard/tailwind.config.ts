import type { Config } from 'tailwindcss';

const config: Config = {
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
      },
    },
  },
  plugins: [],
};

export default config;
