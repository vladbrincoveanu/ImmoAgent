export type AlertTestRecord = {
  telegram_chat_id?: string | null;
  email?: string | null;
  confirmed?: boolean;
};

export type AlertKeywordRecord = {
  keywords?: unknown;
  keyword?: unknown;
};

export type AlertTestChannels = {
  telegram: boolean;
  email: boolean;
  error?: string;
  warning?: string;
};

const EMAIL_CONFIRMATION_WARNING = 'Confirm your email before testing email delivery.';

export function normalizeAlertKeywords(alert: AlertKeywordRecord): string[] {
  const keywords = Array.isArray(alert.keywords)
    ? alert.keywords
      .filter((keyword): keyword is string => (
        typeof keyword === 'string' && keyword.trim().length > 0
      ))
      .map((keyword) => keyword.trim())
    : [];
  if (keywords.length) return keywords;

  return typeof alert.keyword === 'string' && alert.keyword.trim().length > 0
    ? [alert.keyword.trim()]
    : [];
}

export function testChannels(alert: AlertTestRecord): AlertTestChannels {
  const telegram = Boolean(alert.telegram_chat_id);
  const hasEmail = Boolean(alert.email);
  const email = hasEmail && Boolean(alert.confirmed);

  if (telegram || email) {
    return telegram && hasEmail && !alert.confirmed
      ? { telegram, email, warning: EMAIL_CONFIRMATION_WARNING }
      : { telegram, email };
  }

  return {
    telegram: false,
    email: false,
    error: hasEmail
      ? EMAIL_CONFIRMATION_WARNING
      : 'No usable alert channel.',
  };
}

export function testErrorStatus(input: {
  telegramUnavailable: boolean;
  emailFailed: boolean;
}): 502 | 503 {
  return input.telegramUnavailable && !input.emailFailed ? 503 : 502;
}
