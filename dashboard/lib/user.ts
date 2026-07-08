import { NextResponse, type NextRequest } from 'next/server';
import crypto from 'crypto';
import type { Db } from 'mongodb';
import { getServerSession } from 'next-auth';
import { authOptions } from './auth';
import { isProProfile } from './profile';

export const COOKIE_NAME = 'immo_user';
export const FREE_SAVED_SEARCH_LIMIT = 3;

export function getOrCreateUserId(req: NextRequest): string {
  const existing = req.cookies.get(COOKIE_NAME)?.value;
  if (existing) return existing;
  return `u_${crypto.randomBytes(12).toString('hex')}`;
}

export function setUserCookie(res: NextResponse, userId: string): void {
  res.cookies.set(COOKIE_NAME, userId, { maxAge: 60 * 60 * 24 * 365, httpOnly: false, sameSite: 'lax' });
}

// Entitlement lives in the `users` collection: { _id: <user_id>, is_pro: boolean }.
// No doc (or is_pro falsy) = free tier. Pro is flipped manually in Mongo until
// payments exist: db.users.updateOne({_id:'u_...'},{$set:{is_pro:true}},{upsert:true})
// Admin session (role === 'admin') always grants Pro.
export async function isPro(db: Db, userId: string): Promise<boolean> {
  const session = await getServerSession(authOptions);
  if ((session?.user as { role?: string })?.role === 'admin') return true;
  const user = await db.collection('users').findOne({ _id: userId as never }, { projection: { is_pro: 1 } });
  return Boolean(user?.is_pro);
}

/**
 * Freemium gate for persona profiles: non-default profiles are Pro-only.
 * Returns { pro, denied } — when `denied` is set, the route must return it
 * (402 + reason 'pro_profiles', same shape as the saved-search/alert gates).
 */
export async function gateProfile(
  req: NextRequest,
  db: Db,
  profile: string,
): Promise<{ pro: boolean; denied: NextResponse | null }> {
  const pro = await isPro(db, getOrCreateUserId(req));
  if (!pro && isProProfile(profile)) {
    return {
      pro,
      denied: NextResponse.json(
        { error: 'Persona profiles are a Pro feature', reason: 'pro_profiles' },
        { status: 402 },
      ),
    };
  }
  return { pro, denied: null };
}
