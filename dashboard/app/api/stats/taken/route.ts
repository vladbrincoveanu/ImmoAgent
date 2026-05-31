import { NextRequest, NextResponse } from 'next/server';
import { getDb } from '@/lib/mongodb';

export async function GET(request: NextRequest) {
  const db = getDb();
  if (!db) return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });

  const { searchParams } = new URL(request.url);
  const days = Math.min(parseInt(searchParams.get('days') || '30'), 365);

  try {
    const now = Date.now();
    const cutoff = now - days * 86400 * 1000;

    const totalActive = await db.collection('listings').countDocuments({
      $or: [{ listing_status: { $ne: 'taken' } }, { listing_status: null }]
    });
    const totalTaken = await db.collection('listings').countDocuments({
      listing_status: 'taken'
    });
    const total = totalActive + totalTaken;
    const takenRate = total > 0 ? (totalTaken / total * 100) : 0;

    const bySource = await db.collection('listings').aggregate([
      {
        $group: {
          _id: '$source_enum',
          active: {
            $sum: { $cond: [{ $or: [{ $eq: ['$listing_status', null] }, { $ne: ['$listing_status', 'taken'] }] }, 1, 0] }
          },
          taken: { $sum: { $cond: [{ $eq: ['$listing_status', 'taken'] }, 1, 0] } }
        }
      }
    ]).toArray();

    const byDistrict = await db.collection('listings').aggregate([
      {
        $group: {
          _id: '$bezirk',
          active: {
            $sum: { $cond: [{ $or: [{ $eq: ['$listing_status', null] }, { $ne: ['$listing_status', 'taken'] }] }, 1, 0] }
          },
          taken: { $sum: { $cond: [{ $eq: ['$listing_status', 'taken'] }, 1, 0] } }
        }
      }
    ]).toArray();

    const timingPipeline = [
      { $match: { listing_status: 'taken', taken_at: { $exists: true } } },
      {
        $project: {
          days_active: {
            $divide: [
              { $subtract: ['$taken_at', { $ifNull: ['$first_scraped_at', '$processed_at'] }] },
              86400000
            ]
          }
        }
      },
      { $group: {
        _id: null,
        avg_days_active: { $avg: '$days_active' },
        min_days_active: { $min: '$days_active' },
        max_days_active: { $max: '$days_active' }
      }}
    ];
    const timing = await db.collection('listings').aggregate(timingPipeline).toArray();

    const pricePipeline = [
      { $match: { $or: [{ listing_status: 'taken' }, { listing_status: null }] } },
      { $group: {
        _id: '$listing_status',
        avg_price: { $avg: '$price_total' }
      }}
    ];
    const priceStats = await db.collection('listings').aggregate(pricePipeline).toArray();

    const avgPriceActive = priceStats.find(p => p._id === null || p._id !== 'taken')?.avg_price || 0;
    const avgPriceTaken = priceStats.find(p => p._id === 'taken')?.avg_price || 0;

    const alterationsPipeline = [
      { $match: { listing_status: 'taken', 'price_history.0': { $exists: true } } },
      { $project: {
        title: 1,
        price_at_scrape: 1,
        last_price: { $arrayElemAt: ['$price_history.price_total', -1] },
        delta: { $subtract: ['$price_total', { $arrayElemAt: ['$price_history.price_total', -1] }] }
      }},
      { $match: { delta: { $ne: 0 } } },
      { $limit: 5 }
    ];
    const alterationExamples = await db.collection('listings').aggregate(alterationsPipeline).toArray();

    return NextResponse.json({
      summary: { total_active: totalActive, total_taken: totalTaken, total, taken_rate_pct: Math.round(takenRate * 10) / 10 },
      by_source: bySource.map(s => ({
        source: s._id,
        active: s.active,
        taken: s.taken,
        taken_rate: s.active + s.taken > 0 ? Math.round((s.taken / (s.active + s.taken)) * 1000) / 10 : 0
      })),
      by_district: byDistrict.map(d => ({
        bezirk: d._id,
        active: d.active,
        taken: d.taken,
        taken_rate: d.active + d.taken > 0 ? Math.round((d.taken / (d.active + d.taken)) * 1000) / 10 : 0
      })),
      timing: timing[0] ? {
        avg_days_active: Math.round(timing[0].avg_days_active * 10) / 10,
        min_days_active: Math.round(timing[0].min_days_active * 10) / 10,
        max_days_active: Math.round(timing[0].max_days_active * 10) / 10
      } : { avg_days_active: 0, min_days_active: 0, max_days_active: 0 },
      price: {
        avg_price_active: Math.round(avgPriceActive),
        avg_price_taken: Math.round(avgPriceTaken)
      },
      price_alterations: {
        count_with_changes: alterationExamples.length,
        examples: alterationExamples
      }
    });
  } catch (err) {
    console.error('[/api/stats/taken]', err);
    return NextResponse.json({ error: 'Database error' }, { status: 500 });
  }
}