import { NextRequest, NextResponse } from 'next/server';
import { getDb } from '@/lib/mongodb';
import { validateDistrict, validateMinScore } from '@/lib/validators';
import { normalizeProfile } from '@/lib/profile';
import { gateProfile } from '@/lib/user';

export const dynamic = 'force-dynamic';

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const minScore = validateMinScore(searchParams.get('min_score'));
  const district = validateDistrict(searchParams.get('district'));
  const profile = normalizeProfile(searchParams.get('profile'));
  const maxPrice = Number(searchParams.get('max_price') ?? 0) || null;
  const showUnfinanceable = searchParams.get('unfinanceable') === 'true';

  const db = getDb();
  if (!db) return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });
  const { denied } = await gateProfile(request, db, profile);
  if (denied) return denied;

  const match: Record<string, unknown> = {
    url_is_valid: { $ne: false },
    listing_status: { $ne: 'taken' },
    price_total: { $gt: 0 },
    area_m2: { $gt: 0 },
  };
  if (minScore > 0) {
    match.$or = [{ [`scores.${profile}`]: { $gte: minScore } }, { [`scores.${profile}`]: { $exists: false } }];
  }
  if (district) match.bezirk = district;
  if (maxPrice) (match as { price_total: unknown }).price_total = { $gt: 0, $lte: maxPrice };

  try {
    const [agg] = await db.collection('listings').aggregate<{
      _id: null;
      count: number;
      avg_price: number;
      avg_price_per_m2: number;
      avg_score: number;
      below_avg_count: number;
      good_transit_count: number;
      unfinanceable_count: number;
      district_count: number;
    }>([
      { $match: match },
      {
        $addFields: {
          effective_score: { $ifNull: [`$scores.${profile}`, '$score'] },
          price_per_m2: { $divide: ['$price_total', '$area_m2'] },
        },
      },
      {
        $group: {
          _id: null,
          count: { $sum: 1 },
          avg_price: { $avg: '$price_total' },
          avg_price_per_m2: { $avg: { $divide: ['$price_total', '$area_m2'] } },
          avg_score: { $avg: { $ifNull: [`$scores.${profile}`, '$score'] } },
          unfinanceable_count: {
            $sum: {
              $cond: [
                {
                  $and: [
                    { $gt: ['$estimated_down_pct', 30] },
                    { $ne: ['$bank_score_confidence', 'low'] },
                  ],
                },
                1,
                0,
              ],
            },
          },
          district_count: { $addToSet: '$bezirk' },
        },
      },
      {
        $addFields: {
          district_count: { $size: '$district_count' },
        },
      },
    ]).toArray();

    // Below avg + good transit computed in a second pass per district
    const districts = (agg?.district_count ?? 0) > 0
      ? (district ? [district] : await db.collection('listings').distinct('bezirk', { ...match, bezirk: { $exists: true, $ne: null } }))
      : [];

    let belowAvgCount = 0;
    let goodTransitCount = 0;
    if (districts.length > 0) {
      const zoneAvgs = await db.collection('listings').aggregate<{ _id: string; avg_price: number }>([
        { $match: { bezirk: { $in: districts }, price_total: { $gt: 0 }, area_m2: { $gt: 0 }, listing_status: { $ne: 'taken' } } },
        { $group: { _id: '$bezirk', avg_price: { $avg: '$price_total' } } },
      ]).toArray();
      const zoneAvgMap: Record<string, number> = {};
      for (const z of zoneAvgs) zoneAvgMap[z._id] = z.avg_price;

      const allListings = await db.collection('listings').find(match, { projection: { price_total: 1, bezirk: 1, ubahn_walk_minutes: 1 } }).toArray();
      for (const l of allListings) {
        const za = zoneAvgMap[l.bezirk as string];
        if (za && l.price_total != null && l.price_total <= za * 0.9) belowAvgCount += 1;
        if (typeof l.ubahn_walk_minutes === 'number' && l.ubahn_walk_minutes <= 5) goodTransitCount += 1;
      }
    }

    const total = agg?.count ?? 0;
    const visible = showUnfinanceable ? total : Math.max(0, total - (agg?.unfinanceable_count ?? 0));

    return NextResponse.json({
      total,
      visible,
      unfinanceable_count: agg?.unfinanceable_count ?? 0,
      avg_price: agg?.avg_price ? Math.round(agg.avg_price) : null,
      avg_price_per_m2: agg?.avg_price_per_m2 ? Math.round(agg.avg_price_per_m2) : null,
      avg_score: agg?.avg_score ? Math.round(agg.avg_score * 10) / 10 : null,
      district_count: agg?.district_count ?? 0,
      below_avg_count: belowAvgCount,
      good_transit_count: goodTransitCount,
      best_deal_pct: total > 0 ? Math.round((belowAvgCount / total) * 100) : 0,
    });
  } catch (err) {
    console.error('[/api/insights]', err);
    return NextResponse.json({ error: 'Database error' }, { status: 500 });
  }
}
