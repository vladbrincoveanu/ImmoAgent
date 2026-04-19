import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'Immo Scouter Dashboard',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="font-dm-sans">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet" />
      </head>
      <body className="font-dm-sans">
        <header className="h-12 border-b border-gray-200 bg-white flex items-center px-4 shrink-0">
          <a href="/dashboard" className="text-sm font-medium text-gray-700 hover:text-gray-900">Dashboard</a>
          <a href="/dashboard/map" className="ml-4 text-sm font-medium text-gray-700 hover:text-gray-900">Map</a>
        </header>
        {children}
      </body>
    </html>
  );
}
