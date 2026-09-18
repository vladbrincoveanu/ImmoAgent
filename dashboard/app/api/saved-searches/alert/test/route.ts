import { NextRequest, NextResponse } from 'next/server';
import { getDb, ObjectId } from '@/lib/mongodb';
import { getOrCreateUserId, setUserCookie } from '@/lib/user';

export const dynamic = 'force-dynamic';

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

  const alert = await db.collection('alert_subscriptions').findOne({
    _id: new ObjectId(id),
    user_id: userId,
  });
  if (!alert) return NextResponse.json({ error: 'Not found' }, { status: 404 });

  const chatId = alert.telegram_chat_id as string | null;
  if (!chatId) {
    return NextResponse.json(
      { error: 'Dieser Alert hat keine Telegram Chat-ID.' }, { status: 400 });
  }

  const token = process.env.TELEGRAM_MAIN_BOT_TOKEN;
  if (!token) {
    return NextResponse.json(
      { error: 'TELEGRAM_MAIN_BOT_TOKEN ist nicht gesetzt.' }, { status: 503 });
  }

  const keywords: string[] = Array.isArray(alert.keywords)
    ? alert.keywords
    : (alert.keyword ? [alert.keyword] : []);
  const text = [
    '✅ Testnachricht von ImmoScouter.',
    `Alert: ${keywords.length ? keywords.join(', ') : '(alle Treffer)'}`,
    'Diese Chat-ID funktioniert — echte Treffer kommen hier an.',
  ].join('\n');

  const telegram = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ chat_id: chatId, text }),
  });
  if (!telegram.ok) {
    const detail = await telegram.text().catch(() => '');
    return NextResponse.json(
      { error: `Telegram lehnte die Nachricht ab: ${detail.slice(0, 200)}` },
      { status: 502 },
    );
  }

  const res = NextResponse.json({ ok: true });
  setUserCookie(res, userId);
  return res;
}
