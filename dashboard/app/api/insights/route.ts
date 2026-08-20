import { NextRequest, NextResponse } from 'next/server';
import { getDb } from '@/lib/mongodb';
import type { Db } from 'mongodb';
import { validateDistrict, validateMinScore } from '@/lib/validators';
import { DEFAULT_PROFILE, isValidProfile } from '@/lib/profile';

export const dynamic = 'force-dynamic';

type SecondaryCounts = {
  belowAvgCount: number;
  goodTransitCount: number;
};

async function computeSecondaryCounts(
  db: Db,
  match: Record<string, unknown>,
  district: string | null,
): Promise<SecondaryCounts> {
  const districtMatch = district
    ? { bezirk: district }
    : { bezirk: { $exists: true, $ne: null } };

  try {
    const [summary] = await db.collection('listings').aggregate<SecondaryCounts>([
      {
        $match: {
          ...districtMatch,
          listing_status: { $ne: 'taken' },
          price_total: { $gt: 0 },
          area_m2: { $gt: 0 },
        },
      },
      {
        $setWindowFields: {
          partitionBy: '$bezirk',
          sortBy: { _id: 1 },
          output: {
            district_avg_price: {
              $avg: '$price_total',
              window: { documents: ['unbounded', 'unbounded'] },
            },
          },
        },
      },
      { $match: match },
      {
        $group: {
          _id: null,
          belowAvgCount: {
            $sum: {
              $cond: [
                { $lte: ['$price_total', { $multiply: ['$district_avg_price', 0.9] }] },
                1,
                0,
              ],
            },
          },
          goodTransitCount: {
            $sum: {
              $cond: [{ $lte: ['$ubahn_walk_minutes', 5] }, 1, 0],
            },
          },
        },
      },
    ]).toArray();

    return {
      belowAvgCount: summary?.belowAvgCount ?? 0,
      goodTransitCount: summary?.goodTransitCount ?? 0,
    };
  } catch (err) {
    // MongoDB versions before 5.0 do not support $setWindowFields. Keep the
    // fallback cursor-bounded so older deployments do not materialize all rows.
    console.warn('[/api/insights] Falling back from $setWindowFields', err);
    const zoneStats = await db.collection('listings').aggregate<{ _id: string; avg_price: number }>([
      { $match: { ...districtMatch, listing_status: { $ne: 'taken' }, price_total: { $gt: 0 }, area_m2: { $gt: 0 } } },
      { $group: { _id: '$bezirk', avg_price: { $avg: '$price_total' } } },
    ]).toArray();
    const zoneAvgMap: Record<string, number> = {};
    for (const zone of zoneStats) zoneAvgMap[zone._id] = zone.avg_price;

    let belowAvgCount = 0;
    let goodTransitCount = 0;
    const cursor = db.collection('listings').find(match, {
      projection: { price_total: 1, bezirk: 1, ubahn_walk_minutes: 1 },
    });
    for await (const listing of cursor) {
      const zoneAverage = zoneAvgMap[listing.bezirk as string];
      if (zoneAverage && listing.price_total != null && listing.price_total <= zoneAverage * 0.9) {
        belowAvgCount += 1;
      }
      if (typeof listing.ubahn_walk_minutes === 'number' && listing.ubahn_walk_minutes <= 5) {
        goodTransitCount += 1;
      }
    }
    return { belowAvgCount, goodTransitCount };
  }
}

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const minScore = validateMinScore(searchParams.get('min_score'));
  const district = validateDistrict(searchParams.get('district'));
  const profileParam = searchParams.get('profile');
  const profile = isValidProfile(profileParam) ? (profileParam as string) : DEFAULT_PROFILE;
  const maxPrice = Number(searchParams.get('max_price') ?? 0) || null;
  const showUnfinanceable = searchParams.get('unfinanceable') === 'true';

  const db = getDb();
  if (!db) return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });

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

    const { belowAvgCount, goodTransitCount } = (agg?.district_count ?? 0) > 0
      ? await computeSecondaryCounts(db, match, district)
      : { belowAvgCount: 0, goodTransitCount: 0 };

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
    }, {
      headers: { 'Cache-Control': 'public, max-age=15, s-maxage=15, stale-while-revalidate=60' },
    });
  } catch (err) {
    console.error('[/api/insights]', err);
    return NextResponse.json({ error: 'Database error' }, { status: 500 });
  }
}
