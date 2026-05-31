import { NextRequest, NextResponse } from 'next/server';
import { getDb } from '@/lib/mongodb';

export async function GET(request: NextRequest) {
  const db = getDb();
  if (!db) return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });

  const { searchParams } = new URL(request.url);
  const days = Math.min(parseInt(searchParams.get('days') || '30'), 365);

  const now = Date.now();
  const cutoff = new Date(now - days * 86400 * 1000);

  try {
    const createdPipeline = [
      { $match: { processed_at: { $gte: cutoff.getTime() / 1000 } } },
      {
        $group: {
          _id: { $dateToString: { format: '%Y-%m-%d', date: { $toDate: { $multiply: ['$processed_at', 1000] } } } },
          count: { $sum: 1 }
        }
      },
      { $sort: { _id: 1 } }
    ];

    const takenPipeline = [
      { $match: { listing_status: 'taken', taken_at: { $gte: cutoff } } },
      {
        $group: {
          _id: { $dateToString: { format: '%Y-%m-%d', date: '$taken_at' } },
          count: { $sum: 1 }
        }
      },
      { $sort: { _id: 1 } }
    ];

    const [created, taken] = await Promise.all([
      db.collection('listings').aggregate(createdPipeline).toArray(),
      db.collection('listings').aggregate(takenPipeline).toArray()
    ]);

    return NextResponse.json({
      created: created.map(c => ({ date: c._id, count: c.count })),
      taken: taken.map(t => ({ date: t._id, count: t.count }))
    });
  } catch (err) {
    console.error('[/api/stats/timeline]', err);
    return NextResponse.json({ error: 'Database error' }, { status: 500 });
  }
}