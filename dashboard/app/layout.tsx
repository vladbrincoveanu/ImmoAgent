import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Immo Scouter Dashboard',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className="font-dm-sans h-full">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet" />
      </head>
      <body className="font-dm-sans bg-[#F9F7F4] h-full">
        {children}
      </body>
    </html>
  );
}
