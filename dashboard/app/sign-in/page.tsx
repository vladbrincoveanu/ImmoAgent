'use client';
import { signIn } from 'next-auth/react';
import { useSearchParams } from 'next/navigation';
import { useState, Suspense } from 'react';

function SignInForm() {
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const searchParams = useSearchParams();
  const callbackUrl = searchParams.get('callbackUrl') ?? '/dashboard';

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError('');
    const form = new FormData(e.currentTarget);
    const result = await signIn('credentials', {
      email: form.get('email'),
      password: form.get('password'),
      redirect: false,
    });
    if (result?.error) {
      setError('Invalid email or password.');
      setLoading(false);
    } else {
      window.location.href = callbackUrl;
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#F9F7F4]">
      <div className="w-full max-w-sm px-4">
        <div className="bg-white border border-[#E8E4E0] rounded-2xl shadow-sm px-8 py-10">
          <div className="mb-8">
            <h1 className="text-xl font-semibold text-[#2D2D2D] mb-1">Immo Scouter</h1>
            <p className="text-sm text-[#6B6867]">Vienna Property Intelligence</p>
          </div>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-medium text-[#3D405B] mb-1.5">Email</label>
              <input
                name="email"
                type="email"
                required
                autoComplete="email"
                className="w-full rounded-lg border border-[#E8E4E0] bg-[#F9F7F4] px-3 py-2.5 text-sm text-[#2D2D2D] placeholder:text-[#A8A4A0] focus:outline-none focus:ring-2 focus:ring-[#3D405B]/20 focus:border-[#3D405B] transition-colors"
                placeholder="you@example.com"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-[#3D405B] mb-1.5">Password</label>
              <input
                name="password"
                type="password"
                required
                autoComplete="current-password"
                className="w-full rounded-lg border border-[#E8E4E0] bg-[#F9F7F4] px-3 py-2.5 text-sm text-[#2D2D2D] placeholder:text-[#A8A4A0] focus:outline-none focus:ring-2 focus:ring-[#3D405B]/20 focus:border-[#3D405B] transition-colors"
                placeholder="••••••••"
              />
            </div>
            {error && (
              <p className="text-xs text-red-600 bg-red-50 border border-red-100 rounded-lg px-3 py-2">
                {error}
              </p>
            )}
            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-[#3D405B] text-white text-sm font-medium py-2.5 hover:bg-[#2D2D2D] transition-colors disabled:opacity-50 disabled:cursor-not-allowed mt-2"
            >
              {loading ? 'Signing in…' : 'Sign in'}
            </button>
          </form>
        </div>
        <p className="mt-4 text-center text-[11px] text-[#A8A4A0]">
          © 2026 Immo Scouter · Vienna Property Intelligence
        </p>
      </div>
    </div>
  );
}

export default function SignInPage() {
  return (
    <Suspense>
      <SignInForm />
    </Suspense>
  );
}
