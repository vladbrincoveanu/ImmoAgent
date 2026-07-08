import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import UserMenu from '@/components/UserMenu';

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const session = await getServerSession(authOptions);

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <header className="h-12 border-b border-[#E8E4E0] bg-white flex items-center px-4 shrink-0">
        <a href="/dashboard" className="text-sm font-medium text-[#3D405B] hover:text-[#2D2D2D]">Dashboard</a>
        <a href="/dashboard/map" className="ml-4 text-sm font-medium text-[#3D405B] hover:text-[#2D2D2D]">Map</a>
        <div className="ml-auto">
          <UserMenu email={session?.user?.email ?? ''} />
        </div>
      </header>
      <div className="flex-1 min-h-0 overflow-hidden">
        {children}
      </div>
      <footer className="h-8 border-t border-[#E8E4E0] bg-white shrink-0 flex items-center px-4">
        <p className="text-[11px] text-[#A8A4A0]">© 2026 Immo Scouter · Vienna Property Intelligence</p>
      </footer>
    </div>
  );
}
