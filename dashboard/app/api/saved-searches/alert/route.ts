import { NextRequest, NextResponse } from 'next/server';
import { getDb, ObjectId } from '@/lib/mongodb';
import crypto from 'crypto';
import { sendMail, confirmationEmail } from '@/lib/mailer';
import { COOKIE_NAME, getOrCreateUserId, setUserCookie, isPro } from '@/lib/user';

export const dynamic = 'force-dynamic';

interface SubscribeBody {
  email?: string;
  saved_search_id?: string;
  params?: Record<string, string>;
  frequency?: 'instant' | 'daily' | 'weekly';
  /** Which feed to watch. 'listings' is the original behaviour and stays the
   * default so existing callers are unaffected. */
  kind?: 'listings' | 'coop_private';
  /** Free-text match for coop_private alerts, tested against title, address and
   * the ad body by the poller. */
  keyword?: string;
  /** Telegram destination. Either this or an email is required — a co-op
   * Weitergabe is gone in hours, and email is often too slow to be the only
   * channel. */
  telegram_chat_id?: string;
}

const KEYWORD_MAX_LEN = 80;

/** A Telegram chat id is a signed integer (channels are negative, often -100…).
 * Rejecting @usernames on purpose: resolving one needs a bot API round trip, and
 * a silently unresolvable handle is an alert that never arrives. */
function isValidChatId(s: string): boolean {
  return /^-?\d{5,20}$/.test(s);
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
  if (!(await isPro(db, userId))) {
    const res = NextResponse.json({
      error: 'upgrade_required',
      reason: 'alerts_pro_only',
    }, { status: 402 });
    setUserCookie(res, userId);
    return res;
  }
  let body: SubscribeBody = {};
  try { body = await req.json(); } catch { body = {}; }
  const email = (body.email ?? '').trim().toLowerCase();
  const telegramChatId = (body.telegram_chat_id ?? '').trim();
  const hasEmail = !!email && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
  const hasTelegram = !!telegramChatId && isValidChatId(telegramChatId);

  if (telegramChatId && !hasTelegram) {
    return NextResponse.json({ error: 'Invalid Telegram chat id' }, { status: 400 });
  }
  // At least one reachable channel, or the alert is a record of nothing.
  if (!hasEmail && !hasTelegram) {
    return NextResponse.json(
      { error: 'Valid email or Telegram chat id required' }, { status: 400 });
  }
  if (email && !hasEmail) {
    return NextResponse.json({ error: 'Valid email required' }, { status: 400 });
  }

  const kind = body.kind ?? 'listings';
  if (!['listings', 'coop_private'].includes(kind)) {
    return NextResponse.json({ error: 'Invalid kind' }, { status: 400 });
  }
  const keyword = (body.keyword ?? '').toString().trim().slice(0, KEYWORD_MAX_LEN);
  const frequency = body.frequency ?? 'daily';
  if (!['instant', 'daily', 'weekly'].includes(frequency)) {
    return NextResponse.json({ error: 'Invalid frequency' }, { status: 400 });
  }

  const params = body.params ?? {};
  const confirmToken = crypto.randomBytes(24).toString('hex');
  const doc = {
    _id: new ObjectId(),
    user_id: userId,
    email: hasEmail ? email : null,
    telegram_chat_id: hasTelegram ? telegramChatId : null,
    kind,
    keyword,
    saved_search_id: body.saved_search_id ?? null,
    params,
    frequency,
    // Telegram needs no double opt-in: supplying a chat id the bot can post to is
    // itself the consent, and there is no third party to protect from spam. Email
    // still does — anyone can type someone else's address.
    confirmed: !hasEmail && hasTelegram,
    confirm_token: confirmToken,
    created_at: new Date(),
  };
  await db.collection('alert_subscriptions').insertOne(doc);

  const appUrl = process.env.NEXT_PUBLIC_APP_URL ?? process.env.VERCEL_URL
    ? `https://${process.env.VERCEL_URL}`
    : 'http://localhost:3000';
  const confirmUrl = `${appUrl}/api/saved-searches/confirm?token=${confirmToken}`;
  // Telegram-only alerts have no address to confirm — sending here would mail ''.
  const mailResult = hasEmail
    ? await sendMail({
        to: email,
        subject: 'Confirm your ImmoScouter listing alert',
        html: confirmationEmail(email, params, confirmUrl),
      })
    : { ok: false as const, error: 'Telegram-only alert — no email to confirm.' };

  const res = NextResponse.json({
    ok: true,
    subscription_id: doc._id.toString(),
    email: doc.email,
    telegram_chat_id: doc.telegram_chat_id,
    kind,
    keyword,
    frequency,
    confirmed: doc.confirmed,
    email_sent: mailResult.ok,
    message: mailResult.ok
      ? 'Subscription created. Check your inbox to confirm.'
      : doc.confirmed
        ? 'Subscription active — alerts will arrive on Telegram.'
        : `Subscription created. ${mailResult.error ?? 'Email sending unavailable.'}`,
  }, { status: 201 });
  setUserCookie(res, userId);
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
    email: s.email ?? null,
    telegram_chat_id: s.telegram_chat_id ?? null,
    kind: s.kind ?? 'listings',
    keyword: s.keyword ?? null,
    confirmed: !!s.confirmed,
    frequency: s.frequency,
    params: s.params,
    created_at: s.created_at,
  })) });
}
