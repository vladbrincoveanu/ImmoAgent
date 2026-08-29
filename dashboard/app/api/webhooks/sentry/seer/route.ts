import { createHmac, timingSafeEqual } from 'crypto';
import { NextRequest, NextResponse } from 'next/server';
import { getDb } from '@/lib/mongodb';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

const SEER_ACTIONS = [
  'root_cause_started',
  'root_cause_completed',
  'solution_started',
  'solution_completed',
  'coding_started',
  'coding_completed',
  'pr_created',
] as const;

type SeerAction = typeof SEER_ACTIONS[number];
type JsonRecord = Record<string, unknown>;

interface SeerWebhookRecord {
  _id: string;
  request_id: string;
  resource: 'seer';
  action: SeerAction;
  actor: { id: string; name: string; type: string };
  data: JsonRecord;
  installation_uuid: string;
  run_id: number;
  group_id: number;
  webhook_timestamp: string;
  received_at: Date;
}

const COMPLETED_ACTION_DATA: Partial<Record<SeerAction, string>> = {
  root_cause_completed: 'root_cause',
  solution_completed: 'solution',
  coding_completed: 'code_changes',
  pr_created: 'pull_requests',
};

const MAX_TIMESTAMP_AGE_SECONDS = 300;
const WEBHOOK_COLLECTION = 'sentry_seer_webhooks';

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function isSafeInteger(value: unknown): value is number {
  return typeof value === 'number' && Number.isSafeInteger(value);
}

function isSeerAction(value: unknown): value is SeerAction {
  return typeof value === 'string' && (SEER_ACTIONS as readonly string[]).includes(value);
}

function isFreshTimestamp(value: string): boolean {
  const timestamp = Number(value);
  if (!Number.isFinite(timestamp)) return false;
  return Math.abs(Date.now() / 1000 - timestamp) <= MAX_TIMESTAMP_AGE_SECONDS;
}

function hasValidSignature(rawBody: string, signature: string, secret: string): boolean {
  if (!/^[a-f0-9]{64}$/i.test(signature)) return false;
  const expected = createHmac('sha256', secret).update(rawBody, 'utf8').digest();
  const received = Buffer.from(signature, 'hex');
  return received.length === expected.length && timingSafeEqual(expected, received);
}

function parsePayload(value: unknown): {
  action: SeerAction;
  actor: { id: string; name: string; type: string };
  data: JsonRecord & { run_id: number; group_id: number };
  installation: { uuid: string };
} | null {
  if (!isRecord(value) || !isSeerAction(value.action)) return null;
  if (!isRecord(value.actor)
    || typeof value.actor.id !== 'string'
    || typeof value.actor.name !== 'string'
    || typeof value.actor.type !== 'string') {
    return null;
  }
  if (!isRecord(value.data)
    || !isSafeInteger(value.data.run_id)
    || !isSafeInteger(value.data.group_id)) {
    return null;
  }
  if (!isRecord(value.installation) || typeof value.installation.uuid !== 'string'
    || !value.installation.uuid.trim()) {
    return null;
  }

  const actionData = COMPLETED_ACTION_DATA[value.action];
  if (actionData && (value.action === 'pr_created'
    ? !Array.isArray(value.data[actionData])
    : !isRecord(value.data[actionData]))) {
    return null;
  }

  return {
    action: value.action,
    actor: {
      id: value.actor.id,
      name: value.actor.name,
      type: value.actor.type,
    },
    data: value.data as JsonRecord & { run_id: number; group_id: number },
    installation: { uuid: value.installation.uuid },
  };
}

function isDuplicateKeyError(error: unknown): boolean {
  return isRecord(error) && error.code === 11000;
}

function acceptedResponse(requestId: string, action: SeerAction, duplicate: boolean) {
  return NextResponse.json({
    ok: true,
    duplicate,
    request_id: requestId,
    action,
  }, { status: duplicate ? 200 : 202 });
}

/**
 * Receives Sentry's Seer Issue Fix lifecycle webhooks.
 *
 * Sentry retries webhook requests, so Request-ID is used as Mongo's unique
 * `_id`. The full validated data object is retained for later notification or
 * audit tooling; no work is performed synchronously beyond this idempotent
 * write, keeping the response within Sentry's one-second webhook deadline.
 */
export async function POST(req: NextRequest) {
  const secret = process.env.SENTRY_SEER_CLIENT_SECRET?.trim();
  if (!secret) return NextResponse.json({ error: 'Webhook unavailable' }, { status: 503 });

  const resource = req.headers.get('Sentry-Hook-Resource')?.trim().toLowerCase();
  if (resource !== 'seer') {
    return NextResponse.json({ error: 'Invalid webhook resource' }, { status: 400 });
  }

  const requestId = req.headers.get('Request-ID')?.trim();
  const timestamp = req.headers.get('Sentry-Hook-Timestamp')?.trim();
  const signature = req.headers.get('Sentry-Hook-Signature')?.trim();
  if (!requestId || requestId.length > 200 || !timestamp || !signature) {
    return NextResponse.json({ error: 'Invalid webhook headers' }, { status: 400 });
  }
  if (!isFreshTimestamp(timestamp)) {
    return NextResponse.json({ error: 'Expired webhook timestamp' }, { status: 400 });
  }

  let rawBody: string;
  try {
    rawBody = await req.text();
  } catch {
    return NextResponse.json({ error: 'Invalid webhook body' }, { status: 400 });
  }
  if (!hasValidSignature(rawBody, signature, secret)) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  let rawPayload: unknown;
  try {
    rawPayload = JSON.parse(rawBody);
  } catch {
    return NextResponse.json({ error: 'Invalid webhook payload' }, { status: 400 });
  }
  if (isRecord(rawPayload) && typeof rawPayload.action === 'string'
    && !isSeerAction(rawPayload.action)) {
    return NextResponse.json({ error: 'Unsupported Seer action' }, { status: 400 });
  }
  const payload = parsePayload(rawPayload);
  if (!payload) {
    return NextResponse.json({ error: 'Invalid Seer payload' }, { status: 400 });
  }

  const db = getDb();
  if (!db) return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });

  const record: SeerWebhookRecord = {
    _id: requestId,
    request_id: requestId,
    resource,
    action: payload.action,
    actor: payload.actor,
    data: payload.data,
    installation_uuid: payload.installation.uuid,
    run_id: payload.data.run_id,
    group_id: payload.data.group_id,
    webhook_timestamp: timestamp,
    received_at: new Date(),
  };

  try {
    const result = await db.collection<SeerWebhookRecord>(WEBHOOK_COLLECTION).updateOne(
      { _id: requestId },
      { $setOnInsert: record },
      { upsert: true },
    );
    return acceptedResponse(requestId, payload.action, result.upsertedCount === 0);
  } catch (error) {
    // Two concurrent deliveries with the same Request-ID can race before the
    // built-in _id uniqueness check; both are still safe to acknowledge.
    if (isDuplicateKeyError(error)) return acceptedResponse(requestId, payload.action, true);
    console.error('[/api/webhooks/sentry/seer POST]', error);
    return NextResponse.json({ error: 'Database error' }, { status: 500 });
  }
}
