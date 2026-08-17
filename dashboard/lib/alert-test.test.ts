import { describe, expect, it } from '@jest/globals';
import { normalizeAlertKeywords, testChannels, testErrorStatus } from './alert-test';

describe('testChannels', () => {
  it('allows a confirmed email without Telegram', () => {
    expect(testChannels({
      telegram_chat_id: null,
      email: 'u@example.at',
      confirmed: true,
    })).toEqual({ telegram: false, email: true });
  });

  it('rejects an unconfirmed email when Telegram is absent', () => {
    expect(testChannels({
      telegram_chat_id: null,
      email: 'u@example.at',
      confirmed: false,
    })).toEqual({
      telegram: false,
      email: false,
      error: 'Confirm your email before testing email delivery.',
    });
  });

  it('allows Telegram while email confirmation is pending', () => {
    expect(testChannels({
      telegram_chat_id: '-100123456',
      email: 'u@example.at',
      confirmed: false,
    })).toEqual({
      telegram: true,
      email: false,
      warning: 'Confirm your email before testing email delivery.',
    });
  });

  it('allows both channels after email confirmation', () => {
    expect(testChannels({
      telegram_chat_id: '-100123456',
      email: 'u@example.at',
      confirmed: true,
    })).toEqual({ telegram: true, email: true });
  });

  it('rejects an alert with no destination', () => {
    expect(testChannels({
      telegram_chat_id: null,
      email: null,
      confirmed: false,
    })).toEqual({
      telegram: false,
      email: false,
      error: 'No usable alert channel.',
    });
  });
});

describe('testErrorStatus', () => {
  it('uses 502 when email fails despite Telegram being unavailable', () => {
    expect(testErrorStatus({ telegramUnavailable: true, emailFailed: true }))
      .toBe(502);
  });

  it('uses 503 for Telegram-only configuration failure', () => {
    expect(testErrorStatus({ telegramUnavailable: true, emailFailed: false }))
      .toBe(503);
  });

  it('uses 502 for a Telegram provider failure', () => {
    expect(testErrorStatus({ telegramUnavailable: false, emailFailed: false }))
      .toBe(502);
  });
});

describe('normalizeAlertKeywords', () => {
  it('uses non-empty string keywords when present', () => {
    expect(normalizeAlertKeywords({
      keywords: ['  Ablöse  ', '', 42, null],
      keyword: 'legacy',
    })).toEqual(['Ablöse']);
  });

  it('falls back to a valid scalar keyword for malformed arrays', () => {
    expect(normalizeAlertKeywords({
      keywords: [{ bad: true }, null, 42],
      keyword: 'Legacy term',
    })).toEqual(['Legacy term']);
  });

  it('returns no keywords for malformed values without a scalar fallback', () => {
    expect(normalizeAlertKeywords({ keywords: [{ bad: true }], keyword: 42 }))
      .toEqual([]);
  });
});
