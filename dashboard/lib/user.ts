import type { NextRequest, NextResponse } from 'next/server';
import crypto from 'crypto';
import type { Db } from 'mongodb';

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
export async function isPro(db: Db, userId: string): Promise<boolean> {
  const user = await db.collection('users').findOne({ _id: userId as never }, { projection: { is_pro: 1 } });
  return Boolean(user?.is_pro);
}
