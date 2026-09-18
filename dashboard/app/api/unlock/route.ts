import { NextRequest, NextResponse } from 'next/server';
import crypto from 'crypto';
import { getDb } from '@/lib/mongodb';
import { getOrCreateUserId, setUserCookie } from '@/lib/user';

export const dynamic = 'force-dynamic';

/** Shared-secret unlock for Pro features, so the owner (and anyone they hand the
 * password to) can use alerts before payments exist. The alternative was
 * flipping `is_pro` by hand in Mongo for every browser profile.
 *
 * The check is server-side on purpose: the client never learns the password and
 * cannot mark itself Pro, because the only thing that grants entitlement is the
 * `users` doc this route writes. */

const ATTEMPT_LIMIT = 5;
const ATTEMPT_WINDOW_MS = 15 * 60 * 1000;

/** Best-effort brute-force brake. In-process, so it resets on redeploy and is
 * per-instance on serverless — it slows a guesser down, it does not stop a
 * determined one. Use a long password; this is not a substitute for one. */
const attempts = new Map<string, { count: number; first: number }>();

function tooManyAttempts(key: string, now: number): boolean {
  const rec = attempts.get(key);
  if (!rec || now - rec.first > ATTEMPT_WINDOW_MS) return false;
  return rec.count >= ATTEMPT_LIMIT;
}

function recordFailure(key: string, now: number): void {
  const rec = attempts.get(key);
  if (!rec || now - rec.first > ATTEMPT_WINDOW_MS) {
    attempts.set(key, { count: 1, first: now });
    return;
  }
  rec.count += 1;
}

/** Constant-time compare. A plain `===` leaks the shared secret's length and
 * matching prefix through timing, and this endpoint is public. */
function matches(supplied: string, expected: string): boolean {
  const a = Buffer.from(supplied);
  const b = Buffer.from(expected);
  // timingSafeEqual throws on a length mismatch, which would itself be an
  // oracle — hash both sides first so the compared buffers are always 32 bytes.
  const ha = crypto.createHash('sha256').update(a).digest();
  const hb = crypto.createHash('sha256').update(b).digest();
  return crypto.timingSafeEqual(ha, hb);
}

export async function POST(req: NextRequest) {
  const expected = process.env.PRO_UNLOCK_PASSWORD ?? '';
  // No password configured means the feature is off, not open. Failing closed
  // here is what keeps a missing env var from unlocking Pro for everyone.
  if (!expected) {
    return NextResponse.json(
      { error: 'unlock_not_configured' }, { status: 503 });
  }

  const db = getDb();
  if (!db) return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });

  const userId = getOrCreateUserId(req);
  const now = Date.now();
  const throttleKey =
    req.headers.get('x-forwarded-for')?.split(',')[0].trim() || userId;
  if (tooManyAttempts(throttleKey, now)) {
    return NextResponse.json(
      { error: 'too_many_attempts' }, { status: 429 });
  }

  let supplied = '';
  try {
    const body = await req.json();
    supplied = typeof body?.password === 'string' ? body.password : '';
  } catch {
    supplied = '';
  }

  if (!supplied || !matches(supplied, expected)) {
    recordFailure(throttleKey, now);
    const res = NextResponse.json({ error: 'invalid_password' }, { status: 401 });
    setUserCookie(res, userId);
    return res;
  }

  attempts.delete(throttleKey);
  try {
    await db.collection('users').updateOne(
      { _id: userId as never },
      { $set: { is_pro: true, unlocked_at: new Date(), unlocked_via: 'password' } },
      { upsert: true },
    );
  } catch (err) {
    console.error('[/api/unlock POST]', err);
    return NextResponse.json({ error: 'Database error' }, { status: 500 });
  }

  const res = NextResponse.json({ ok: true, is_pro: true });
  setUserCookie(res, userId);
  return res;
}
