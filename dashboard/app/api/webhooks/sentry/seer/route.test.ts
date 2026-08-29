import { createHmac } from 'crypto';
import { beforeEach, describe, expect, it, jest } from '@jest/globals';
import type { NextRequest } from 'next/server';

const SECRET = 'test-client-secret';
const REQUEST_ID = 'request-123';
const INSTALLATION_UUID = 'a8e5d37a-696c-4c54-adb5-b3f28d64c7de';

const mockUpdateOne = jest.fn<() => Promise<{ upsertedCount: number }>>();
const mockCollection = { updateOne: mockUpdateOne };
const mockDb = { collection: jest.fn(() => mockCollection) };
const mockGetDb = jest.fn();

jest.mock('@/lib/mongodb', () => ({
  getDb: mockGetDb,
}), { virtual: true });

import { POST } from './route';

function payload(overrides: Record<string, unknown> = {}) {
  return {
    action: 'root_cause_started',
    actor: { id: 'sentry', name: 'Sentry', type: 'application' },
    data: { run_id: 12345, group_id: 1170820242 },
    installation: { uuid: INSTALLATION_UUID },
    ...overrides,
  };
}

function sign(rawBody: string): string {
  return createHmac('sha256', SECRET).update(rawBody, 'utf8').digest('hex');
}

function request(
  body = payload(),
  options: {
    requestId?: string;
    resource?: string;
    timestamp?: string;
    signature?: string;
    rawBody?: string;
  } = {},
): NextRequest {
  const rawBody = options.rawBody ?? JSON.stringify(body);
  const timestamp = options.timestamp ?? String(Math.floor(Date.now() / 1000));
  return {
    text: async () => rawBody,
    headers: new Headers({
      'Content-Type': 'application/json',
      'Request-ID': options.requestId ?? REQUEST_ID,
      'Sentry-Hook-Resource': options.resource ?? 'seer',
      'Sentry-Hook-Timestamp': timestamp,
      'Sentry-Hook-Signature': options.signature ?? sign(rawBody),
    }),
  } as unknown as NextRequest;
}

async function responseBody(response: Response): Promise<Record<string, unknown>> {
  return response.json() as Promise<Record<string, unknown>>;
}

beforeEach(() => {
  jest.clearAllMocks();
  process.env.SENTRY_SEER_CLIENT_SECRET = SECRET;
  mockGetDb.mockReturnValue(mockDb);
  mockUpdateOne.mockResolvedValue({ upsertedCount: 1 });
});

describe('POST /api/webhooks/sentry/seer', () => {
  it('accepts and stores a signed Seer event', async () => {
    const res = await POST(request());
    const body = await responseBody(res);

    expect(res.status).toBe(202);
    expect(body).toEqual({
      ok: true,
      duplicate: false,
      request_id: REQUEST_ID,
      action: 'root_cause_started',
    });
    expect(mockCollection.updateOne).toHaveBeenCalledWith(
      { _id: REQUEST_ID },
      expect.objectContaining({
        $setOnInsert: expect.objectContaining({
          request_id: REQUEST_ID,
          resource: 'seer',
          action: 'root_cause_started',
          run_id: 12345,
          group_id: 1170820242,
          installation_uuid: INSTALLATION_UUID,
        }),
      }),
      { upsert: true },
    );
  });

  it('returns success without inserting a duplicate request ID', async () => {
    mockUpdateOne.mockResolvedValue({ upsertedCount: 0 });

    const res = await POST(request());
    const body = await responseBody(res);

    expect(res.status).toBe(200);
    expect(body.duplicate).toBe(true);
  });

  it('rejects a missing or invalid signature before touching Mongo', async () => {
    const res = await POST(request(payload(), { signature: 'not-a-valid-signature' }));
    const body = await responseBody(res);

    expect(res.status).toBe(401);
    expect(body).toEqual({ error: 'Unauthorized' });
    expect(mockGetDb).not.toHaveBeenCalled();
    expect(mockUpdateOne).not.toHaveBeenCalled();
  });

  it('rejects a non-Seer resource even when the request is signed', async () => {
    const res = await POST(request(payload(), { resource: 'issue' }));
    const body = await responseBody(res);

    expect(res.status).toBe(400);
    expect(body).toEqual({ error: 'Invalid webhook resource' });
    expect(mockUpdateOne).not.toHaveBeenCalled();
  });

  it('rejects unsupported actions and incomplete common fields', async () => {
    const unsupported = await POST(request(payload({ action: 'issue_created' })));
    const unsupportedBody = await responseBody(unsupported);
    expect(unsupported.status).toBe(400);
    expect(unsupportedBody).toEqual({ error: 'Unsupported Seer action' });

    const incomplete = await POST(request(payload({
      data: { run_id: '12345', group_id: 1170820242 },
    })));
    const incompleteBody = await responseBody(incomplete);
    expect(incomplete.status).toBe(400);
    expect(incompleteBody).toEqual({ error: 'Invalid Seer payload' });
    expect(mockUpdateOne).not.toHaveBeenCalled();
  });

  it('rejects replayed requests outside the timestamp window', async () => {
    const staleTimestamp = String(Math.floor(Date.now() / 1000) - 301);
    const res = await POST(request(payload(), { timestamp: staleTimestamp }));
    const body = await responseBody(res);

    expect(res.status).toBe(400);
    expect(body).toEqual({ error: 'Expired webhook timestamp' });
    expect(mockUpdateOne).not.toHaveBeenCalled();
  });

  it('fails closed when the client secret is not configured', async () => {
    delete process.env.SENTRY_SEER_CLIENT_SECRET;

    const res = await POST(request());
    const body = await responseBody(res);

    expect(res.status).toBe(503);
    expect(body).toEqual({ error: 'Webhook unavailable' });
    expect(mockGetDb).not.toHaveBeenCalled();
  });
});
