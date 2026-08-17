import { describe, expect, it } from '@jest/globals';
import { testChannels } from './alert-test';

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
    })).toEqual({ telegram: true, email: false });
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
