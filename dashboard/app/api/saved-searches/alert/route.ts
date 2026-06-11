import { NextRequest, NextResponse } from 'next/server';
import { getDb, ObjectId } from '@/lib/mongodb';
import crypto from 'crypto';

export const dynamic = 'force-dynamic';

const COOKIE_NAME = 'immo_user';

function getOrCreateUserId(req: NextRequest): string {
  const existing = req.cookies.get(COOKIE_NAME)?.value;
  if (existing) return existing;
  return `u_${crypto.randomBytes(12).toString('hex')}`;
}

interface SubscribeBody {
  email?: string;
  saved_search_id?: string;
  params?: Record<string, string>;
  frequency?: 'instant' | 'daily' | 'weekly';
}

// POST /api/saved-searches/alert
// Body: { email, saved_search_id OR params, frequency }
// Stores a subscription record. In production this would also enqueue
// an email send (via e.g. Resend/SES/Postmark), but here we record the
// lead so the team can follow up.
export async function POST(req: NextRequest) {
  const db = getDb();
  if (!db) return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });
  const userId = getOrCreateUserId(req);
  let body: SubscribeBody = {};
  try { body = await req.json(); } catch { body = {}; }
  const email = (body.email ?? '').trim().toLowerCase();
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return NextResponse.json({ error: 'Valid email required' }, { status: 400 });
  }
  const frequency = body.frequency ?? 'daily';
  if (!['instant', 'daily', 'weekly'].includes(frequency)) {
    return NextResponse.json({ error: 'Invalid frequency' }, { status: 400 });
  }

  const params = body.params ?? {};
  const doc = {
    _id: new ObjectId(),
    user_id: userId,
    email,
    saved_search_id: body.saved_search_id ?? null,
    params,
    frequency,
    confirmed: false,
    created_at: new Date(),
  };
  await db.collection('alert_subscriptions').insertOne(doc);

  const res = NextResponse.json({
    ok: true,
    subscription_id: doc._id.toString(),
    email,
    frequency,
    message: 'Subscription created. Confirmation email would be sent in production.',
  }, { status: 201 });
  res.cookies.set(COOKIE_NAME, userId, { maxAge: 60 * 60 * 24 * 365, httpOnly: false, sameSite: 'lax' });
  return res;
}

export async function GET(req: NextRequest) {
  const userId = req.cookies.get(COOKIE_NAME)?.value;
  if (!userId) return NextResponse.json({ items: [] });
  const db = getDb();
  if (!db) return NextResponse.json({ items: [] });
  const items = await db.collection('alert_subscriptions')
    .find({ user_id: userId })
    .sort({ created_at: -1 })
    .limit(20)
    .toArray();
  return NextResponse.json({ items: items.map((s) => ({
    _id: s._id.toString(),
    email: s.email,
    frequency: s.frequency,
    params: s.params,
    created_at: s.created_at,
  })) });
}
