import { NextRequest, NextResponse } from 'next/server';
import { getDb } from '@/lib/mongodb';

export async function GET(request: NextRequest) {
  const db = getDb();
  if (!db) return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });

  const { searchParams } = new URL(request.url);
  const limit = Math.min(parseInt(searchParams.get('limit') || '50'), 200);
  const offset = parseInt(searchParams.get('offset') || '0');
  const sort = searchParams.get('sort') || 'days_active_desc';

  const sortMap: Record<string, Record<string, 1 | -1>> = {
    days_active_desc: { days_active: -1 },
    taken_at_desc: { taken_at: -1 },
    price_desc: { price_total: -1 },
  };

  try {
    const pipeline = [
      { $match: { listing_status: 'taken' } },
      {
        $project: {
          title: 1,
          url: 1,
          source_enum: 1,
          bezirk: 1,
          price_total: 1,
          price_at_scrape: 1,
          days_active: {
            $divide: [
              { $subtract: ['$taken_at', { $ifNull: ['$first_scraped_at', '$processed_at'] }] },
              86400000
            ]
          },
          first_scraped_at: { $ifNull: ['$first_scraped_at', '$processed_at'] },
          taken_at: 1,
          price_history: 1
        }
      },
      { $sort: sortMap[sort] || sortMap.days_active_desc },
      { $skip: offset },
      { $limit: limit }
    ];

    const [listings, total] = await Promise.all([
      db.collection('listings').aggregate(pipeline).toArray(),
      db.collection('listings').countDocuments({ listing_status: 'taken' })
    ]);

    return NextResponse.json({
      listings: listings.map(l => ({
        _id: l._id.toString(),
        title: l.title,
        url: l.url,
        source_enum: l.source_enum,
        bezirk: l.bezirk,
        price_total: l.price_total,
        price_at_scrape: l.price_at_scrape,
        days_active: Math.round(l.days_active * 10) / 10,
        first_scraped_at: l.first_scraped_at,
        taken_at: l.taken_at
      })),
      total,
      limit,
      offset
    });
  } catch (err) {
    console.error('[/api/stats/taken-listings]', err);
    return NextResponse.json({ error: 'Database error' }, { status: 500 });
  }
}