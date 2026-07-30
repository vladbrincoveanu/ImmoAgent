import { NextRequest, NextResponse } from 'next/server';
import { getDb } from '@/lib/mongodb';

export const dynamic = 'force-dynamic';

/** Mongo's error for `watch()` against a deployment without an oplog. A
 * standalone mongod (the usual local/dev setup) always fails this way, so it is
 * a configuration fact, not a transient fault — the client must be told to stop
 * retrying rather than reconnect forever. */
function isChangeStreamUnsupported(err: unknown): boolean {
  const code = (err as { code?: number } | null)?.code;
  const message = String((err as { message?: string } | null)?.message ?? err);
  return code === 40573 || /only supported on replica sets|\$changeStream/i.test(message);
}

export async function GET(request: NextRequest) {
  const db = getDb();
  if (!db) {
    return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });
  }

  const encoder = new TextEncoder();
  const collection = db.collection('listings');

  let changeStream: ReturnType<typeof collection.watch> | null = null;
  let heartbeat: ReturnType<typeof setInterval> | null = null;
  let closed = false;

  const stream = new ReadableStream({
    async start(controller) {
      const send = (payload: unknown) => {
        if (closed) return;
        try {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(payload)}\n\n`));
        } catch {
          // Controller already closed by a concurrent teardown.
        }
      };

      // Single teardown path for every exit: client disconnect, change-stream
      // error, or unsupported deployment. Previously the request handler parked
      // on a promise that never resolved and an interval that was never
      // cleared, so each connection leaked a cursor plus two timers for the
      // lifetime of the server process.
      const cleanup = () => {
        if (closed) return;
        closed = true;
        if (heartbeat) clearInterval(heartbeat);
        heartbeat = null;
        void changeStream?.close().catch(() => {
          // Cursor may already be dead; nothing left to release.
        });
        changeStream = null;
        try {
          controller.close();
        } catch {
          // Already closed.
        }
      };

      if (request.signal.aborted) {
        cleanup();
        return;
      }
      request.signal.addEventListener('abort', cleanup, { once: true });

      const fail = (err: unknown, stage: string) => {
        if (isChangeStreamUnsupported(err)) {
          // Terminal and expected on a standalone mongod: tell the client so it
          // stops reconnecting instead of hammering the route every 5s.
          console.warn(`SSE ${stage}: change streams unavailable on this deployment`);
          send({ type: 'unsupported', reason: 'change_streams_unavailable' });
        } else {
          console.error(`SSE ${stage} error:`, err);
          send({ type: 'error', reason: 'stream_failed' });
        }
        cleanup();
      };

      try {
        changeStream = collection.watch(
          [{ $match: { operationType: 'insert' } }],
          { fullDocument: 'updateLookup' }
        );

        changeStream.on('change', (change) => {
          if (change.fullDocument) {
            send({ type: 'new_listing', data: change.fullDocument });
          }
        });

        changeStream.on('error', (err) => fail(err, 'change stream'));
      } catch (err) {
        // Unsupported deployments usually surface asynchronously via the error
        // handler above, but a synchronous throw is possible too.
        fail(err, 'setup');
        return;
      }

      heartbeat = setInterval(() => {
        if (closed) return;
        try {
          controller.enqueue(encoder.encode(`: heartbeat\n\n`));
        } catch {
          cleanup();
        }
      }, 30000);
    },

    // Fires when the consumer goes away without an abort signal.
    cancel() {
      if (closed) return;
      closed = true;
      if (heartbeat) clearInterval(heartbeat);
      heartbeat = null;
      void changeStream?.close().catch(() => {});
      changeStream = null;
    },
  });

  return new NextResponse(stream, {
    headers: {
      'Content-Type': 'text/event-stream',
      'Cache-Control': 'no-cache, no-transform',
      'Connection': 'keep-alive',
      'X-Accel-Buffering': 'no',
    },
  });
}
