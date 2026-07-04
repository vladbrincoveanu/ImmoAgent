import { NextResponse } from 'next/server';
import { getDb } from '@/lib/mongodb';

export async function GET() {
  try {
    const db = getDb();
    if (!db) {
      return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });
    }

    const stats = await db
      .collection('listings')
      .aggregate<{ _id: string; avg_price_per_m2: number; count: number }>([
        {
          $match: {
            url_is_valid: { $ne: false },
            listing_status: { $ne: 'taken' },
            price_total: { $gt: 0 },
            area_m2: { $gt: 0 },
            bezirk: { $nin: [null, ''] },
          },
        },
        {
          $group: {
            _id: '$bezirk',
            avg_price_per_m2: { $avg: { $divide: ['$price_total', '$area_m2'] } },
            count: { $sum: 1 },
          },
        },
      ])
      .toArray();

    const districts: Record<string, { avg_price_per_m2: number; count: number }> = {};
    for (const s of stats) {
      if (typeof s._id === 'string' && s._id.length > 0) {
        districts[s._id] = { avg_price_per_m2: Math.round(s.avg_price_per_m2), count: s.count };
      }
    }

    return NextResponse.json({ districts });
  } catch (err) {
    console.error('[/api/district-heatmap]', err);
    return NextResponse.json({ error: 'Database error' }, { status: 500 });
  }
}
