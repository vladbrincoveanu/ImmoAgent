import { beforeEach, describe, expect, it, jest } from '@jest/globals';
import type { NextRequest } from 'next/server';

const mockInsertOne = jest.fn();
const mockCollection = { insertOne: mockInsertOne };
const mockDb = { collection: jest.fn(() => mockCollection) };
const mockGetDb = jest.fn();
const mockGetOrCreateUserId = jest.fn();
const mockSetUserCookie = jest.fn();
const mockSendMail = jest.fn<
  (_options: Record<string, unknown>) => Promise<{ ok: boolean; error?: string }>
>();
const mockConfirmationEmail = jest.fn(() => '<p>confirm</p>');

class MockObjectId {
  constructor(readonly value = '507f1f77bcf86cd799439011') {}

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
  sendMail: mockSendMail,
  confirmationEmail: mockConfirmationEmail,
}), { virtual: true });

import { POST } from './route';

function request(body: Record<string, unknown>): NextRequest {
  return { json: async () => body } as unknown as NextRequest;
}

beforeEach(() => {
  jest.clearAllMocks();
  mockGetDb.mockReturnValue(mockDb);
  mockGetOrCreateUserId.mockReturnValue('user-1');
  mockSendMail.mockResolvedValue({ ok: false, error: 'SMTP unavailable' });
  delete process.env.NEXT_PUBLIC_APP_URL;
  delete process.env.VERCEL_URL;
});

describe('POST /api/saved-searches/alert kinds', () => {
  it('accepts an all-MyGEWO alert kind', async () => {
    const response = await POST(request({
      kind: 'mygewo',
      telegram_chat_id: '-100123456',
    }));
    const body = await response.json() as { kind: string };

    expect(response.status).toBe(201);
    expect(body.kind).toBe('mygewo');
    expect(mockInsertOne).toHaveBeenCalledWith(
      expect.objectContaining({ kind: 'mygewo' }));
  });

  it('rejects an unknown alert kind before storing it', async () => {
    const response = await POST(request({
      kind: 'not-a-feed',
      telegram_chat_id: '-100123456',
    }));
    const body = await response.json() as { error: string };

    expect(response.status).toBe(400);
    expect(body.error).toBe('Invalid kind');
    expect(mockInsertOne).not.toHaveBeenCalled();
  });

  it('uses NEXT_PUBLIC_APP_URL for email confirmation links', async () => {
    process.env.NEXT_PUBLIC_APP_URL = 'https://immo-agent-vienna.vercel.app';
    process.env.VERCEL_URL = 'another-deployment.vercel.app';
    mockSendMail.mockResolvedValue({ ok: true });

    const response = await POST(request({ email: 'user@example.at' }));

    expect(response.status).toBe(201);
    expect(mockConfirmationEmail).toHaveBeenCalledWith(
      'user@example.at',
      {},
      expect.stringContaining(
        'https://immo-agent-vienna.vercel.app/api/saved-searches/confirm?token=',
      ),
    );
  });
});
