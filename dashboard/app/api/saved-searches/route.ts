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

export async function GET(req: NextRequest) {
  const db = getDb();
  if (!db) return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });
  const userId = getOrCreateUserId(req);
  try {
    const items = await db.collection('saved_searches')
      .find({ user_id: userId })
      .sort({ created_at: -1 })
      .limit(50)
      .toArray();
    const res = NextResponse.json({ items: items.map((s) => ({
      _id: s._id.toString(),
      name: s.name,
      params: s.params,
      created_at: s.created_at,
      last_match_count: s.last_match_count ?? null,
    })) });
    res.cookies.set(COOKIE_NAME, userId, { maxAge: 60 * 60 * 24 * 365, httpOnly: false, sameSite: 'lax' });
    return res;
  } catch (err) {
    console.error('[/api/saved-searches GET]', err);
    return NextResponse.json({ error: 'Database error' }, { status: 500 });
  }
}

export async function POST(req: NextRequest) {
  const db = getDb();
  if (!db) return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });
  const userId = getOrCreateUserId(req);
  let body: { name?: string; params?: Record<string, string> } = {};
  try { body = await req.json(); } catch { body = {}; }
  const name = (body.name ?? 'Untitled search').toString().slice(0, 80);
  const params = body.params ?? {};
  try {
    const doc = {
      _id: new ObjectId(),
      user_id: userId,
      name,
      params,
      created_at: new Date(),
    };
    await db.collection('saved_searches').insertOne(doc);
    const res = NextResponse.json({
      _id: doc._id.toString(),
      name: doc.name,
      params: doc.params,
      created_at: doc.created_at.toISOString(),
    }, { status: 201 });
    res.cookies.set(COOKIE_NAME, userId, { maxAge: 60 * 60 * 24 * 365, httpOnly: false, sameSite: 'lax' });
    return res;
  } catch (err) {
    console.error('[/api/saved-searches POST]', err);
    return NextResponse.json({ error: 'Database error' }, { status: 500 });
  }
}

export async function DELETE(req: NextRequest) {
  const db = getDb();
  if (!db) return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });
  const userId = getOrCreateUserId(req);
  const { searchParams } = new URL(req.url);
  const id = searchParams.get('id');
  if (!id) return NextResponse.json({ error: 'Missing id' }, { status: 400 });
  try {
    let oid: ObjectId;
    try { oid = new ObjectId(id); } catch { return NextResponse.json({ error: 'Invalid id' }, { status: 400 }); }
    const result = await db.collection('saved_searches').deleteOne({ _id: oid, user_id: userId });
    return NextResponse.json({ deleted: result.deletedCount });
  } catch (err) {
    console.error('[/api/saved-searches DELETE]', err);
    return NextResponse.json({ error: 'Database error' }, { status: 500 });
  }
}
