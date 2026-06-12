import { NextRequest, NextResponse } from 'next/server';
import { getDb } from '@/lib/mongodb';

export const dynamic = 'force-dynamic';

export async function GET(
  _req: NextRequest,
  { params }: { params: { bezirk: string } }
) {
  const db = getDb();
  if (!db) return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });

  const bezirk = params.bezirk;

  // Aggregate listings by month over the last 12 months.
  // Uses processed_at (Unix seconds) to bucket.
  const since = Math.floor(Date.now() / 1000) - 365 * 24 * 60 * 60;

  const trend = await db.collection('listings').aggregate<{
    _id: { y: number; m: number };
    avg_price: number;
    avg_price_per_m2: number;
    count: number;
  }>([
    {
      $match: {
        bezirk,
        url_is_valid: { $ne: false },
        listing_status: { $ne: 'taken' },
        price_total: { $gt: 0 },
        area_m2: { $gt: 0 },
        processed_at: { $gte: since },
      },
    },
    {
      $addFields: {
        dt: { $toDate: { $multiply: ['$processed_at', 1000] } },
        price_per_m2: { $divide: ['$price_total', '$area_m2'] },
      },
    },
    {
      $group: {
        _id: { y: { $year: '$dt' }, m: { $month: '$dt' } },
        avg_price: { $avg: '$price_total' },
        avg_price_per_m2: { $avg: '$price_per_m2' },
        count: { $sum: 1 },
      },
    },
    { $sort: { '_id.y': 1, '_id.m': 1 } },
  ]).toArray();

  return NextResponse.json({
    bezirk,
    months: trend.map((t) => ({
      ym: `${t._id.y}-${String(t._id.m).padStart(2, '0')}`,
      avg_price: Math.round(t.avg_price),
      avg_price_per_m2: Math.round(t.avg_price_per_m2),
      count: t.count,
    })),
  });
}
