import { NextRequest, NextResponse } from 'next/server';
import { getDb, ObjectId } from '@/lib/mongodb';
import crypto from 'crypto';
import { sendMail, confirmationEmail } from '@/lib/mailer';
import { COOKIE_NAME, getOrCreateUserId, setUserCookie, isPro } from '@/lib/user';
import { isValidAlertEmail } from './email-validation';

export const dynamic = 'force-dynamic';

interface SubscribeBody {
  email?: string;
  saved_search_id?: string;
  params?: Record<string, string>;
  frequency?: 'instant' | 'daily' | 'weekly';
  /** Which feed to watch. 'listings' is the original behaviour and stays the
   * default so existing callers are unaffected. */
  kind?: 'listings' | 'coop_private' | 'keyword';
  /** Free-text match for coop_private alerts, tested against title, address and
   * the ad body by the poller. */
  keyword?: string;
  /** Telegram destination. Either this or an email is required — a co-op
   * Weitergabe is gone in hours, and email is often too slow to be the only
   * channel. */
  telegram_chat_id?: string;
  /** Multiple keys use OR semantics so synonyms do not disable an alert. */
  keywords?: string[];
  /** Optional numeric gates. Missing listing values pass and are flagged later. */
  filters?: {
    min_area?: number; max_area?: number;
    min_rooms?: number; max_rooms?: number;
    max_price?: number;
  };
}

const KEYWORD_MAX_LEN = 80;
const MAX_KEYWORDS = 10;
const FILTER_KEYS = ['min_area', 'max_area', 'min_rooms', 'max_rooms', 'max_price'] as const;

function cleanKeywords(body: SubscribeBody): string[] {
  const values = Array.isArray(body.keywords)
    ? body.keywords
    : (body.keyword ? [body.keyword] : []);
  return values
    .map((key) => String(key).trim().slice(0, KEYWORD_MAX_LEN))
    .filter(Boolean)
    .slice(0, MAX_KEYWORDS);
}

function cleanFilters(raw: SubscribeBody['filters']): Record<string, number> {
  const filters: Record<string, number> = {};
  for (const key of FILTER_KEYS) {
    const value = Number(raw?.[key]);
    if (Number.isFinite(value) && value >= 0) filters[key] = value;
  }
  return filters;
}

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
  const hasEmail = isValidAlertEmail(email);
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
  if (!['listings', 'coop_private', 'keyword'].includes(kind)) {
    return NextResponse.json({ error: 'Invalid kind' }, { status: 400 });
  }
  const keywords = cleanKeywords(body);
  const filters = cleanFilters(body.filters);
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
    keywords,
    // Keep the scalar for older pollers and records.
    keyword: keywords[0] ?? '',
    filters,
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

  const appUrl = process.env.NEXT_PUBLIC_APP_URL
    ?? (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : 'http://localhost:3000');
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
    keywords,
    filters,
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
    keywords: Array.isArray(s.keywords) && s.keywords.length
      ? s.keywords
      : (s.keyword ? [s.keyword] : []),
    keyword: s.keyword ?? null,
    filters: s.filters ?? null,
    confirmed: !!s.confirmed,
    frequency: s.frequency,
    params: s.params,
    created_at: s.created_at,
  })) });
}

export async function DELETE(req: NextRequest) {
  const db = getDb();
  if (!db) return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });
  const userId = getOrCreateUserId(req);
  const id = req.nextUrl.searchParams.get('id') ?? '';
  if (!ObjectId.isValid(id)) {
    return NextResponse.json({ error: 'Invalid id' }, { status: 400 });
  }
  const result = await db.collection('alert_subscriptions').deleteOne({
    _id: new ObjectId(id),
    user_id: userId,
  });
  if (result.deletedCount === 0) {
    return NextResponse.json({ error: 'Not found' }, { status: 404 });
  }
  const res = NextResponse.json({ ok: true });
  setUserCookie(res, userId);
  return res;
}
