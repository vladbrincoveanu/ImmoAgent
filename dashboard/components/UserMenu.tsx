'use client';
import { signOut } from 'next-auth/react';

export default function UserMenu({ email }: { email: string }) {
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-[#6B6867] hidden sm:block">{email}</span>
      <button
        onClick={() => signOut({ callbackUrl: '/sign-in' })}
        className="text-xs text-[#3D405B] hover:text-[#2D2D2D] border border-[#E8E4E0] rounded-md px-2.5 py-1 hover:bg-[#F9F7F4] transition-colors"
      >
        Sign out
      </button>
    </div>
  );
}
