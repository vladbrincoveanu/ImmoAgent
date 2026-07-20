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
      <body className="font-dm-sans bg-[#F9F7F4]">
        <header className="h-12 border-b border-[#E8E4E0] bg-white flex items-center px-4 shrink-0">
          <a href="/dashboard" className="text-sm font-medium text-[#3D405B] hover:text-[#2D2D2D]">Dashboard</a>
          <a href="/dashboard/map" className="ml-4 text-sm font-medium text-[#3D405B] hover:text-[#2D2D2D]">Map</a>
          <a href="/coop" className="ml-4 text-sm font-medium text-[#3D405B] hover:text-[#2D2D2D]">Genossenschaft</a>
        </header>
        {children}
      </body>
    </html>
  );
}
