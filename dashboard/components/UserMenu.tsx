'use client';
import { signOut } from 'next-auth/react';

export default function UserMenu({ email }: { email: string }) {
  if (!email) {
    // Anonymous visitor — low-friction invite to sign in, no hard wall.
    return (
      <a
        href="/sign-in"
        className="text-xs font-medium text-white bg-[#3D405B] hover:bg-[#2D2D2D] rounded-md px-3 py-1.5 transition-colors"
      >
        Sign in
      </a>
    );
  }
  return (
    <div className="flex items-center gap-3">
      <span className="text-xs text-[#6B6867] hidden sm:block">{email}</span>
      <button
        onClick={() => signOut({ callbackUrl: '/dashboard' })}
        className="text-xs text-[#3D405B] hover:text-[#2D2D2D] border border-[#E8E4E0] rounded-md px-2.5 py-1 hover:bg-[#F9F7F4] transition-colors"
      >
        Sign out
      </button>
    </div>
  );
}
