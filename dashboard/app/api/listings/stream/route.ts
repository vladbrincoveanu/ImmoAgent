import { NextResponse } from 'next/server';
import { getDb } from '@/lib/mongodb';

export const dynamic = 'force-dynamic';

export async function GET() {
  const db = getDb();
  if (!db) {
    return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });
  }

  const encoder = new TextEncoder();

  const stream = new ReadableStream({
    async start(controller) {
      let changeStream: Awaited<ReturnType<ReturnType<typeof db.collection>['watch']>> | null = null;

      const sendEvent = (data: unknown) => {
        try {
          controller.enqueue(encoder.encode(`data: ${JSON.stringify(data)}\n\n`));
        } catch {
          // Controller may already be closed
        }
      };

      const heartbeat = setInterval(() => {
        try {
          controller.enqueue(encoder.encode(`: heartbeat\n\n`));
        } catch {
          clearInterval(heartbeat);
        }
      }, 30000);

      try {
        const collection = db.collection('listings');
        changeStream = collection.watch(
          [{ $match: { operationType: 'insert' } }],
          { fullDocument: 'updateLookup' }
        );

        changeStream.on('change', (change) => {
          if (change.fullDocument) {
            sendEvent({ type: 'new_listing', data: change.fullDocument });
          }
        });

        changeStream.on('error', (err) => {
          console.error('SSE change stream error:', err);
          clearInterval(heartbeat);
          try {
            controller.close();
          } catch {
            // Already closed
          }
        });
      } catch (err) {
        console.error('SSE setup error:', err);
        clearInterval(heartbeat);
        try {
          controller.close();
        } catch {
          // Already closed
        }
      }

      // Keep-alive until client disconnects
      await new Promise<void>((resolve) => {
        const checkClose = setInterval(() => {
          // Simple keep-alive
        }, 5000);
        // Note: in production, use proper abort signal handling
      });
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