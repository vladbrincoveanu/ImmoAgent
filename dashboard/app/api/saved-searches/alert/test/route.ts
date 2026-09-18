import { NextRequest, NextResponse } from 'next/server';
import { getDb, ObjectId } from '@/lib/mongodb';
import { getOrCreateUserId, setUserCookie } from '@/lib/user';
import { alertTestEmail, sendMail, SMTP_TIMEOUT_MS } from '@/lib/mailer';
import {
  type AlertKeywordRecord,
  normalizeAlertKeywords,
  testChannels,
  testErrorStatus,
} from '@/lib/alert-test';

export const dynamic = 'force-dynamic';

type AlertTestChannel = 'telegram' | 'email';

type ChannelAttempt = {
  channel: AlertTestChannel;
  ok: boolean;
  error?: string;
  unavailable?: boolean;
};

type AlertTestError = {
  channel: AlertTestChannel;
  message: string;
};

function withDeadline<T>(
  promise: Promise<T>,
  deadline: number,
  label: string,
  onTimeout?: () => void,
): Promise<T> {
  const remaining = deadline - Date.now();
  if (remaining <= 0) {
    onTimeout?.();
    return Promise.reject(new Error(`${label} timed out after ${SMTP_TIMEOUT_MS}ms.`));
  }

  let timer: ReturnType<typeof setTimeout> | undefined;
  const timeout = new Promise<never>((_, reject) => {
    timer = setTimeout(() => {
      onTimeout?.();
      reject(new Error(`${label} timed out after ${SMTP_TIMEOUT_MS}ms.`));
    }, remaining);
  });

  return Promise.race([promise, timeout]).finally(() => {
    if (timer !== undefined) clearTimeout(timer);
  });
}

async function sendTelegramProbe(
  chatId: string | null,
  keys: string[],
): Promise<ChannelAttempt> {
  const token = process.env.TELEGRAM_MAIN_BOT_TOKEN;
  if (!token) {
    return {
      channel: 'telegram',
      ok: false,
      unavailable: true,
      error: 'TELEGRAM_MAIN_BOT_TOKEN is not set.',
    };
  }

  const controller = new AbortController();
  const deadline = Date.now() + SMTP_TIMEOUT_MS;
  const text =
    '✅ Testnachricht von ImmoScouter.\n' +
    `Alert: ${keys.length ? keys.join(', ') : '(alle Treffer)'}\n` +
    'Diese Chat-ID funktioniert — echte Treffer kommen hier an.';

  try {
    const tg = await withDeadline(
      fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ chat_id: chatId, text }),
        signal: controller.signal,
      }),
      deadline,
      'Telegram request',
      () => controller.abort(),
    );
    if (!tg.ok) {
      // Surface Telegram's own reason: "chat not found" and "bot was blocked"
      // need different fixes from the user, and a generic failure hides which.
      let detail: string;
      try {
        detail = await withDeadline(tg.text(), deadline, 'Telegram error detail');
      } catch (err) {
        return {
          channel: 'telegram',
          ok: false,
          error: `Telegram error detail unavailable: ${String(err)}`,
        };
      }
      return {
        channel: 'telegram',
        ok: false,
        error: `Telegram rejected the message: ${detail.slice(0, 200)}`,
      };
    }
    return { channel: 'telegram', ok: true };
  } catch (err) {
    return {
      channel: 'telegram',
      ok: false,
      error: `Telegram request failed: ${String(err)}`,
    };
  }
}

async function sendEmailProbe(email: string, keys: string[]): Promise<ChannelAttempt> {
  try {
    const mail = await withDeadline(
      sendMail({
        to: email,
        subject: 'ImmoScouter Alert-Test',
        html: alertTestEmail(keys),
      }),
      Date.now() + SMTP_TIMEOUT_MS,
      'Email delivery',
    );
    return mail.ok
      ? { channel: 'email', ok: true }
      : {
          channel: 'email',
          ok: false,
          error: `Email delivery failed: ${mail.error ?? 'SMTP provider rejected the message.'}`,
        };
  } catch (err) {
    return {
      channel: 'email',
      ok: false,
      error: `Email delivery failed: ${String(err)}`,
    };
  }
}

/** POST /api/saved-searches/alert/test  { id }
 *
 * Sends one probe message to each usable alert channel.
 *
 * Why this exists: a mistyped chat id is otherwise indistinguishable from a
 * quiet market. The poll logs a send failure nobody reads, the user sees no
 * messages, and concludes days later that alerts are broken. This makes the
 * failure happen at setup time, with the provider's own reason attached. */
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

  const keys = normalizeAlertKeywords(alert as AlertKeywordRecord);
  const chatId = (alert.telegram_chat_id as string | null) ?? null;
  const email = (alert.email as string | null) ?? null;
  const channels = testChannels({
    telegram_chat_id: chatId,
    email,
    confirmed: Boolean(alert.confirmed),
  });
  if (channels.error) {
    return NextResponse.json({
      error: channels.error,
      channels: [],
      sentChannels: [],
      failedChannels: [],
      errors: [],
    }, { status: 400 });
  }

  const attempts: Array<{
    channel: AlertTestChannel;
    promise: Promise<ChannelAttempt>;
  }> = [];
  if (channels.telegram) {
    attempts.push({
      channel: 'telegram',
      promise: sendTelegramProbe(chatId, keys),
    });
  }
  if (channels.email) {
    attempts.push({
      channel: 'email',
      promise: sendEmailProbe(email as string, keys),
    });
  }

  const settled = await Promise.allSettled(attempts.map(({ promise }) => promise));
  const results = settled.map((result, index): ChannelAttempt => (
    result.status === 'fulfilled'
      ? result.value
      : {
          channel: attempts[index].channel,
          ok: false,
          error: `${attempts[index].channel} delivery failed: ${String(result.reason)}`,
        }
  ));
  const sentChannels = results
    .filter((result) => result.ok)
    .map((result) => result.channel);
  const failedChannels = results
    .filter((result) => !result.ok)
    .map((result) => result.channel);
  const errors: AlertTestError[] = results
    .filter((result) => !result.ok)
    .map((result) => ({
      channel: result.channel,
      message: result.error ?? `${result.channel} delivery failed.`,
    }));
  const telegramUnavailable = results.some((result) => (
    result.channel === 'telegram' && !result.ok && result.unavailable
  ));
  const emailFailed = results.some((result) => (
    result.channel === 'email' && !result.ok
  ));
  const responseFields = {
    // Keep `channels` as the response field used by the first dashboard version.
    channels: sentChannels,
    sentChannels,
    failedChannels,
    errors,
    ...(channels.warning ? { warning: channels.warning } : {}),
  };

  if (errors.length) {
    return NextResponse.json(
      {
        error: errors.map(({ message }) => message).join(' '),
        ...responseFields,
      },
      { status: testErrorStatus({ telegramUnavailable, emailFailed }) });
  }

  const res = NextResponse.json({
    ok: true,
    ...responseFields,
  });
  setUserCookie(res, userId);
  return res;
}
