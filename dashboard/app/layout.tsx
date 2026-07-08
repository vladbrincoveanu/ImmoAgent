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
    <html lang="en" className="font-dm-sans h-full">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
        <link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap" rel="stylesheet" />
      </head>
      <body className="font-dm-sans bg-[#F9F7F4] h-screen flex flex-col overflow-hidden">
        <header className="h-12 border-b border-[#E8E4E0] bg-white flex items-center px-4 shrink-0">
          <a href="/dashboard" className="text-sm font-medium text-[#3D405B] hover:text-[#2D2D2D]">Dashboard</a>
          <a href="/dashboard/map" className="ml-4 text-sm font-medium text-[#3D405B] hover:text-[#2D2D2D]">Map</a>
        </header>
        <div className="flex-1 min-h-0 overflow-hidden">
          {children}
        </div>
        <footer className="h-8 border-t border-[#E8E4E0] bg-white shrink-0 flex items-center px-4">
          <p className="text-[11px] text-[#A8A4A0]">© 2026 Immo Scouter · Vienna Property Intelligence</p>
        </footer>
      </body>
    </html>
  );
}
