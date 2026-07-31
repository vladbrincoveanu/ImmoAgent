import { NextRequest, NextResponse } from 'next/server';
import { getDb, ObjectId } from '@/lib/mongodb';
import { getOrCreateUserId, setUserCookie } from '@/lib/user';

export const dynamic = 'force-dynamic';

/** POST /api/saved-searches/alert/test  { id }
 *
 * Sends one probe message to the alert's Telegram chat.
 *
 * Why this exists: a mistyped chat id is otherwise indistinguishable from a
 * quiet market. The poll logs a send failure nobody reads, the user sees no
 * messages, and concludes days later that alerts are broken. This makes the
 * failure happen at setup time, with Telegram's own reason attached. */
export async function POST(req: NextRequest) {
  const db = getDb();
  if (!db) return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });
  const userId = getOrCreateUserId(req);

  let body: { id?: string } = {};
  try { body = await req.json(); } catch { body = {}; }
  const id = (body.id ?? '').trim();
  if (!ObjectId.isValid(id)) {
    return NextResponse.json({ error: 'Invalid id' }, { status: 400 });
  }

  // Scoped to the caller: this endpoint sends a message, so an unscoped lookup
  // would let anyone with an id push text into someone else's Telegram chat.
  const alert = await db.collection('alert_subscriptions').findOne({
    _id: new ObjectId(id),
    user_id: userId,
  });
  if (!alert) return NextResponse.json({ error: 'Not found' }, { status: 404 });

  const chatId = alert.telegram_chat_id as string | null;
  if (!chatId) {
    return NextResponse.json(
      { error: 'This alert has no Telegram chat ID.' }, { status: 400 });
  }

  const token = process.env.TELEGRAM_MAIN_BOT_TOKEN;
  if (!token) {
    return NextResponse.json(
      { error: 'TELEGRAM_MAIN_BOT_TOKEN is not set.' }, { status: 503 });
  }

  const keys: string[] = Array.isArray(alert.keywords) ? alert.keywords : [];
  const text =
    '✅ Testnachricht von ImmoScouter.\n' +
    `Alert: ${keys.length ? keys.join(', ') : '(alle Treffer)'}\n` +
    'Diese Chat-ID funktioniert — echte Treffer kommen hier an.';

  const tg = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chat_id: chatId, text }),
  });
  if (!tg.ok) {
    // Surface Telegram's own reason: "chat not found" and "bot was blocked"
    // need different fixes from the user, and a generic failure hides which.
    const detail = await tg.text().catch(() => '');
    return NextResponse.json(
      { error: `Telegram rejected the message: ${detail.slice(0, 200)}` },
      { status: 502 });
  }

  const res = NextResponse.json({ ok: true });
  setUserCookie(res, userId);
  return res;
}
