export type AlertTestRecord = {
  telegram_chat_id?: string | null;
  email?: string | null;
  confirmed?: boolean;
};

export type AlertTestChannels = {
  telegram: boolean;
  email: boolean;
  error?: string;
};

export function testChannels(alert: AlertTestRecord): AlertTestChannels {
  const telegram = Boolean(alert.telegram_chat_id);
  const hasEmail = Boolean(alert.email);
  const email = hasEmail && Boolean(alert.confirmed);

  if (telegram || email) return { telegram, email };

  return {
    telegram: false,
    email: false,
    error: hasEmail
      ? 'Confirm your email before testing email delivery.'
      : 'No usable alert channel.',
  };
}
