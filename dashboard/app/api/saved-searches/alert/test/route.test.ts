import { afterEach, beforeEach, describe, expect, it, jest } from '@jest/globals';
import type { NextRequest } from 'next/server';

const ALERT_ID = '507f1f77bcf86cd799439011';
const originalFetch = global.fetch;

function response(ok = true, detail = '') {
  return {
    ok,
    text: jest.fn<() => Promise<string>>().mockResolvedValue(detail),
  };
}

const mockFindOne = jest.fn<
  (filter: Record<string, unknown>) => Promise<Record<string, unknown> | null>
>();
const mockCollection = { findOne: mockFindOne };
const mockDb = { collection: jest.fn((_name: string) => mockCollection) };
const mockGetDb = jest.fn<() => typeof mockDb>();
const mockGetOrCreateUserId = jest.fn<(_req: unknown) => string>();
const mockSetUserCookie = jest.fn<(_res: unknown, _id: string) => void>();
const mockSendMail = jest.fn<
  (opts: { to: string; subject: string; html: string }) => Promise<{ ok: boolean; error?: string }>
>();
const mockAlertTestEmail = jest.fn((keywords: string[]) => `HTML:${keywords.join('|')}`);
const mockFetch = jest.fn<
  (_input: unknown, _init?: unknown) => Promise<ReturnType<typeof response>>
>();
const mockObjectIdIsValid = jest.fn<(_id: string) => boolean>();

class MockObjectId {
  static isValid = mockObjectIdIsValid;

  constructor(readonly value: string) {}

  toString() {
    return this.value;
  }
}

jest.mock('@/lib/mongodb', () => ({
  getDb: mockGetDb,
  ObjectId: MockObjectId,
}), { virtual: true });

jest.mock('@/lib/user', () => ({
  getOrCreateUserId: mockGetOrCreateUserId,
  setUserCookie: mockSetUserCookie,
}), { virtual: true });

jest.mock('@/lib/mailer', () => ({
  alertTestEmail: mockAlertTestEmail,
  sendMail: mockSendMail,
}), { virtual: true });

jest.mock('@/lib/alert-test', () => (
  jest.requireActual('../../../../../lib/alert-test')
), { virtual: true });

import { POST } from './route';

function request(id = ALERT_ID): NextRequest {
  return { json: async () => ({ id }) } as unknown as NextRequest;
}

function baseAlert(overrides: Record<string, unknown> = {}) {
  return {
    _id: new MockObjectId(ALERT_ID),
    user_id: 'user-1',
    keywords: ['Ablöse'],
    keyword: 'Ablöse',
    telegram_chat_id: null,
    email: null,
    confirmed: false,
    ...overrides,
  };
}

async function bodyOf(res: Response): Promise<Record<string, unknown>> {
  return res.json() as Promise<Record<string, unknown>>;
}

async function flushMicrotasks() {
  await Promise.resolve();
  await Promise.resolve();
}

beforeEach(() => {
  jest.clearAllMocks();
  mockGetDb.mockReturnValue(mockDb);
  mockGetOrCreateUserId.mockReturnValue('user-1');
  mockObjectIdIsValid.mockReturnValue(true);
  mockFindOne.mockResolvedValue(baseAlert());
  mockSendMail.mockResolvedValue({ ok: true });
  mockFetch.mockResolvedValue(response());
  global.fetch = mockFetch as unknown as typeof fetch;
  delete process.env.TELEGRAM_MAIN_BOT_TOKEN;
});

afterEach(() => {
  global.fetch = originalFetch;
  delete process.env.TELEGRAM_MAIN_BOT_TOKEN;
});

describe('POST /api/saved-searches/alert/test', () => {
  it('sends an email-only probe without calling Telegram', async () => {
    mockFindOne.mockResolvedValue(baseAlert({
      email: 'u@example.at',
      confirmed: true,
      keywords: ['General listing'],
    }));

    const res = await POST(request());
    const body = await bodyOf(res);

    expect(res.status).toBe(200);
    expect(body.sentChannels).toEqual(['email']);
    expect(body.failedChannels).toEqual([]);
    expect(mockFetch).not.toHaveBeenCalled();
    expect(mockSendMail).toHaveBeenCalledWith(expect.objectContaining({
      to: 'u@example.at',
      html: 'HTML:General listing',
    }));
  });

  it('rejects an unconfirmed email-only probe before contacting providers', async () => {
    mockFindOne.mockResolvedValue(baseAlert({
      email: 'u@example.at',
      confirmed: false,
    }));

    const res = await POST(request());
    const body = await bodyOf(res);

    expect(res.status).toBe(400);
    expect(body.error).toBe('Confirm your email before testing email delivery.');
    expect(body.sentChannels).toEqual([]);
    expect(body.failedChannels).toEqual([]);
    expect(body.errors).toEqual([]);
    expect(mockFetch).not.toHaveBeenCalled();
    expect(mockSendMail).not.toHaveBeenCalled();
  });

  it('keeps the alert lookup scoped to the current user', async () => {
    mockFindOne.mockResolvedValue(null);

    const res = await POST(request());

    expect(res.status).toBe(404);
    expect(mockFindOne).toHaveBeenCalledWith({
      _id: expect.any(MockObjectId),
      user_id: 'user-1',
    });
    expect(mockFetch).not.toHaveBeenCalled();
    expect(mockSendMail).not.toHaveBeenCalled();
  });

  it('reports both channels when both probes succeed', async () => {
    process.env.TELEGRAM_MAIN_BOT_TOKEN = 'telegram-token';
    mockFindOne.mockResolvedValue(baseAlert({
      telegram_chat_id: '-100123456',
      email: 'u@example.at',
      confirmed: true,
    }));

    const res = await POST(request());
    const body = await bodyOf(res);

    expect(res.status).toBe(200);
    expect(body.sentChannels).toEqual(['telegram', 'email']);
    expect(body.failedChannels).toEqual([]);
    expect(body.errors).toEqual([]);
    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(mockSendMail).toHaveBeenCalledTimes(1);
  });

  it('tests Telegram and warns when the mixed alert email is unconfirmed', async () => {
    process.env.TELEGRAM_MAIN_BOT_TOKEN = 'telegram-token';
    mockFindOne.mockResolvedValue(baseAlert({
      telegram_chat_id: '-100123456',
      email: 'u@example.at',
      confirmed: false,
    }));

    const res = await POST(request());
    const body = await bodyOf(res);

    expect(res.status).toBe(200);
    expect(body.sentChannels).toEqual(['telegram']);
    expect(body.warning).toBe('Confirm your email before testing email delivery.');
    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(mockSendMail).not.toHaveBeenCalled();
  });

  it('keeps email success when Telegram rejects the probe', async () => {
    process.env.TELEGRAM_MAIN_BOT_TOKEN = 'telegram-token';
    mockFindOne.mockResolvedValue(baseAlert({
      telegram_chat_id: '-100123456',
      email: 'u@example.at',
      confirmed: true,
    }));
    mockFetch.mockResolvedValue(response(false, 'chat not found'));

    const res = await POST(request());
    const body = await bodyOf(res);

    expect(res.status).toBe(502);
    expect(body.sentChannels).toEqual(['email']);
    expect(body.failedChannels).toEqual(['telegram']);
    expect(body.error).toContain('chat not found');
    expect(body.errors).toEqual([
      { channel: 'telegram', message: 'Telegram rejected the message: chat not found' },
    ]);
  });

  it('keeps Telegram success when email delivery fails', async () => {
    process.env.TELEGRAM_MAIN_BOT_TOKEN = 'telegram-token';
    mockFindOne.mockResolvedValue(baseAlert({
      telegram_chat_id: '-100123456',
      email: 'u@example.at',
      confirmed: true,
    }));
    mockSendMail.mockResolvedValue({ ok: false, error: 'SMTP down' });

    const res = await POST(request());
    const body = await bodyOf(res);

    expect(res.status).toBe(502);
    expect(body.sentChannels).toEqual(['telegram']);
    expect(body.failedChannels).toEqual(['email']);
    expect(body.error).toContain('SMTP down');
    expect(body.errors).toEqual([
      { channel: 'email', message: 'Email delivery failed: SMTP down' },
    ]);
  });

  it('starts both channel probes before either provider settles', async () => {
    process.env.TELEGRAM_MAIN_BOT_TOKEN = 'telegram-token';
    mockFindOne.mockResolvedValue(baseAlert({
      telegram_chat_id: '-100123456',
      email: 'u@example.at',
      confirmed: true,
    }));
    let resolveTelegram!: (value: ReturnType<typeof response>) => void;
    let resolveEmail!: (value: { ok: boolean }) => void;
    mockFetch.mockReturnValue(new Promise((resolve) => { resolveTelegram = resolve; }));
    mockSendMail.mockReturnValue(new Promise((resolve) => { resolveEmail = resolve; }));

    const result = POST(request());
    await flushMicrotasks();

    expect(mockFetch).toHaveBeenCalledTimes(1);
    expect(mockSendMail).toHaveBeenCalledTimes(1);

    resolveTelegram(response());
    resolveEmail({ ok: true });
    expect((await result).status).toBe(200);
  });

  it('uses the legacy scalar keyword when the keyword array is malformed', async () => {
    mockFindOne.mockResolvedValue(baseAlert({
      email: 'u@example.at',
      confirmed: true,
      keywords: [{ bad: true }, null, 42],
      keyword: 'Legacy term',
    }));

    const res = await POST(request());

    expect(res.status).toBe(200);
    expect(mockAlertTestEmail).toHaveBeenCalledWith(['Legacy term']);
  });
});
