import { NextRequest, NextResponse } from 'next/server';
import { getDb } from '@/lib/mongodb';

export const dynamic = 'force-dynamic';

export async function GET(req: NextRequest) {
  const token = req.nextUrl.searchParams.get('token');
  if (!token) {
    return NextResponse.redirect(new URL('/?confirmed=error', req.url));
  }
  const db = getDb();
  if (!db) {
    return NextResponse.redirect(new URL('/?confirmed=error', req.url));
  }
  const result = await db.collection('alert_subscriptions').findOneAndUpdate(
    { confirm_token: token, confirmed: false },
    { $set: { confirmed: true, confirmed_at: new Date() } },
  );
  if (!result) {
    return NextResponse.redirect(new URL('/?confirmed=already', req.url));
  }
  return NextResponse.redirect(new URL('/?confirmed=ok', req.url));
}
