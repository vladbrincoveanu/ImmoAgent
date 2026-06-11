import { NextRequest, NextResponse } from 'next/server';
import { getDb } from '@/lib/mongodb';
import { Document, WithId } from 'mongodb';
import { validateDistrict, validateSort, validateMinScore, validateLimit, validateStatus } from '@/lib/validators';
import { DEFAULT_PROFILE, isValidProfile } from '@/lib/profile';
import { resolveCoordinates } from '@/lib/district-centroids';
// eslint-disable-next-line @typescript-eslint/no-require-imports
const config = require('../../../../config.json');

type ListingDocument = Document;

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const limit = validateLimit(searchParams.get('limit'), 100);
  const minScore = validateMinScore(searchParams.get('min_score'));
  const district = validateDistrict(searchParams.get('district'));
  const sort = validateSort(searchParams.get('sort'));

  const profileParam = searchParams.get('profile');
  const profile = isValidProfile(profileParam) ? (profileParam as string) : DEFAULT_PROFILE;
  if (profileParam && !isValidProfile(profileParam)) {
    console.warn('[/api/listings/top] Invalid profile rejected:', profileParam);
  }

  const sortOptions: Record<string, Record<string, 1 | -1>> = {
    score_desc:
      profile === DEFAULT_PROFILE
        ? { score: -1, processed_at: -1 }
        : { [`scores.${profile}`]: -1, processed_at: -1 },
    price_asc: { price_total: 1 },
    price_desc: { price_total: -1 },
    date_desc: { processed_at: -1 },
    area_desc: { area_m2: -1 },
  };
  const sortBy = sortOptions[sort] ?? sortOptions.score_desc;

  try {
    const db = getDb();
    if (!db) {
      return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });
    }
    if (district === null && searchParams.get('district') !== null) {
      console.warn('[/api/listings/top] Invalid district rejected:', searchParams.get('district'));
    }
    const andConditions: Record<string, unknown>[] = [
      { url_is_valid: { $ne: false } },
      { listing_status: { $ne: "taken" } },
      { price_total: { $gt: 0 } },
      { area_m2: { $gt: 0 } },
      { $expr: { $gte: [{ $divide: ["$price_total", "$area_m2"] }, 2500] } },
      { $expr: { $lte: [{ $divide: ["$price_total", "$area_m2"] }, 20000] } },
      { title: { $nin: [null, ""] } },
    ];

    if (minScore > 0) {
      andConditions.push({
        $or: [
          { score: { $gte: minScore } },
          { score: null },
        ],
      });
    }

    if (district) {
      andConditions.push({ bezirk: district });
    }

    const status = validateStatus(searchParams.get('status'));
    if (status !== 'all') {
      if (status === 'active') {
        andConditions.push({ listing_status: { $ne: "taken" } });
      } else if (status === 'taken') {
        andConditions.push({ listing_status: "taken" });
      }
    }

    const belowAvgPct = Math.max(0, Math.min(100, Number(searchParams.get('below_avg_pct') ?? 0)));
    if (belowAvgPct > 0) {
      andConditions.push({ bezirk: { $exists: true, $ne: null } });
    }

    const filter: Record<string, unknown> = { $and: andConditions };

    const listings = await db
      .collection<ListingDocument>('listings')
      .find(filter)
      .sort(sortBy)
      .limit(limit)
      .toArray();

    // Compute district avg prices for zone-vs-avg calculation
    const districts = Array.from(new Set(listings.map((l) => l.bezirk).filter((d): d is string => typeof d === 'string' && d.length > 0)));
    const zoneAvgMap: Record<string, number> = {};
    if (districts.length > 0) {
      const zoneStats = await db.collection('listings').aggregate<{ _id: string; avg_price: number; avg_price_per_m2: number }>([
        {
          $match: {
            bezirk: { $in: districts },
            url_is_valid: { $ne: false },
            listing_status: { $ne: 'taken' },
            price_total: { $gt: 0 },
            area_m2: { $gt: 0 },
          },
        },
        { $group: { _id: '$bezirk', avg_price: { $avg: '$price_total' }, avg_price_per_m2: { $avg: { $divide: ['$price_total', '$area_m2'] } } } },
      ]).toArray();
      for (const z of zoneStats) zoneAvgMap[z._id] = z.avg_price;
    }

    const PRICE_PER_SQM = (config?.PRICE_PER_SQM as number | undefined) ?? 7000;

    const result = listings.map((l: WithId<ListingDocument>) => {
      const hasPrice = typeof l.price_total === 'number' && l.price_total > 0;
      const price_is_estimated = !hasPrice && typeof l.area_m2 === 'number' && l.area_m2 > 0;
      const price_total = hasPrice
        ? l.price_total
        : price_is_estimated
          ? Math.round(l.area_m2 * PRICE_PER_SQM)
          : null;

      const scores = (l as { scores?: Record<string, number | null> }).scores;
      const bezirkStr = typeof l.bezirk === 'string' ? l.bezirk : null;
      const zoneAvg = bezirkStr ? zoneAvgMap[bezirkStr] : undefined;
      const priceVsAvgPct = price_total != null && zoneAvg && zoneAvg > 0
        ? Math.round(((price_total - zoneAvg) / zoneAvg) * 100)
        : null;
      return {
        _id: l._id.toString(),
        title: l.title,
        url: l.url,
        source_enum: l.source_enum,
        bezirk: l.bezirk,
        price_total,
        area_m2: l.area_m2,
        rooms: l.rooms,
        score: (scores?.[profile] ?? l.score ?? null) as number | null,
        scores: scores ?? null,
        profile,
        processed_at: l.processed_at,
        image_url: l.image_url || l.minio_image_path || null,
        url_is_valid: l.url_is_valid !== false,
        price_is_estimated,
        estimated_down_pct: l.estimated_down_pct ?? undefined,
        estimated_down_pct_kimv: l.estimated_down_pct_kimv ?? undefined,
        estimated_equity_eur: l.estimated_equity_eur ?? undefined,
        bank_score_confidence: l.bank_score_confidence ?? undefined,
        coordinate_source: l.coordinate_source ?? undefined,
        price_vs_avg_pct: priceVsAvgPct,
        ubahn_walk_minutes: typeof l.ubahn_walk_minutes === 'number' ? l.ubahn_walk_minutes : null,
        coordinates: resolveCoordinates(l.coordinates as { lat: number; lon: number } | null | undefined, l.bezirk as string | null | undefined),
      };
    });

    const finalResult = belowAvgPct > 0
      ? result.filter((l) => l.price_vs_avg_pct != null && l.price_vs_avg_pct <= -belowAvgPct)
      : result;

    return NextResponse.json({ listings: finalResult, total: finalResult.length });
  } catch (err) {
    console.error('[/api/listings/top]', err);
    return NextResponse.json({ error: 'Database error' }, { status: 500 });
  }
}