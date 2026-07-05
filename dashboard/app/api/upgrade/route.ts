import { NextRequest, NextResponse } from 'next/server';
import { getDb } from '@/lib/mongodb';
import { getOrCreateUserId, setUserCookie } from '@/lib/user';

export const dynamic = 'force-dynamic';

// Paywall email capture. Stores an upgrade request lead; Pro is granted
// manually in Mongo (users collection) until payments exist.
export async function POST(req: NextRequest) {
  const db = getDb();
  if (!db) return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });
  const userId = getOrCreateUserId(req);
  let body: { email?: string; reason?: string } = {};
  try { body = await req.json(); } catch { body = {}; }
  const email = (body.email ?? '').trim().toLowerCase();
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return NextResponse.json({ error: 'Valid email required' }, { status: 400 });
  }
  const reason = (body.reason ?? 'unknown').toString().slice(0, 60);
  try {
    await db.collection('upgrade_requests').updateOne(
      { user_id: userId, email },
      {
        $set: { reason, updated_at: new Date() },
        $setOnInsert: { user_id: userId, email, created_at: new Date() },
      },
      { upsert: true },
    );
    const res = NextResponse.json({ ok: true });
    setUserCookie(res, userId);
    return res;
  } catch (err) {
    console.error('[/api/upgrade POST]', err);
    return NextResponse.json({ error: 'Database error' }, { status: 500 });
  }
}
