import { NextRequest, NextResponse } from 'next/server';
import { getDb } from '@/lib/mongodb';
import { getOrCreateUserId, setUserCookie, isPro, FREE_SAVED_SEARCH_LIMIT } from '@/lib/user';

export const dynamic = 'force-dynamic';

export async function GET(req: NextRequest) {
  const db = getDb();
  if (!db) return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });
  const userId = getOrCreateUserId(req);
  try {
    const [pro, count] = await Promise.all([
      isPro(db, userId),
      db.collection('saved_searches').countDocuments({ user_id: userId }),
    ]);
    const res = NextResponse.json({
      is_pro: pro,
      saved_search_count: count,
      saved_search_limit: pro ? null : FREE_SAVED_SEARCH_LIMIT,
    });
    setUserCookie(res, userId);
    return res;
  } catch (err) {
    console.error('[/api/me GET]', err);
    return NextResponse.json({ error: 'Database error' }, { status: 500 });
  }
}
