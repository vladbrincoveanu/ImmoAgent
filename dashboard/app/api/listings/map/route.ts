import { NextRequest, NextResponse } from 'next/server';
import { getDb } from '@/lib/mongodb';
import { MapListing } from '@/lib/types';
import { Document, WithId } from 'mongodb';
import { validateDistrict, validateSort, validateMinScore, validateLimit } from '@/lib/validators';
import { DEFAULT_PROFILE, isValidProfile } from '@/lib/profile';
import { resolveCoordinates } from '@/lib/district-centroids';
// eslint-disable-next-line @typescript-eslint/no-require-imports
const config = require('../../../../config.json');

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const limit = validateLimit(searchParams.get('limit'), 200);
  const minScore = validateMinScore(searchParams.get('min_score'));
  const district = validateDistrict(searchParams.get('district'));
  const sort = validateSort(searchParams.get('sort'));
  const genossenschaft = searchParams.get('genossenschaft') === 'true';

  const profileParam = searchParams.get('profile');
  const profile = isValidProfile(profileParam) ? (profileParam as string) : DEFAULT_PROFILE;
  if (profileParam && !isValidProfile(profileParam)) {
    console.warn('[/api/listings/map] Invalid profile rejected:', profileParam);
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
      console.warn('[/api/listings/map] Invalid district rejected:', searchParams.get('district'));
    }
    const filter: Record<string, unknown> = {
      $and: [
        { url_is_valid: { $ne: false } },
        { listing_status: { $ne: "taken" } },
        { price_total: { $gt: 0 } },
        { area_m2: { $gt: 0 } },
        { $expr: { $gte: [{ $divide: ["$price_total", "$area_m2"] }, 2500] } },
        { $expr: { $lte: [{ $divide: ["$price_total", "$area_m2"] }, 20000] } },
        { title: { $nin: [null, ""] } },
      ],
    };

    // min_score is applied AFTER mapping (below), on the profile-resolved
    // score the client actually displays — the raw `score` field can differ
    // from scores.<profile> and filtering on it lets mismatches leak through.

    if (district) {
      filter.bezirk = district;
    }

    if (genossenschaft) {
      (filter.$and as Record<string, unknown>[]).push({ is_genossenschaft: true });
    }

    const listings = await db
      .collection<Document>('listings')
      .find(filter)
      .sort(sortBy)
      .limit(limit)
      .toArray();

    // Compute district avg price for zone-vs-avg calculation (single aggregation)
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

    const result: MapListing[] = listings.map((l: WithId<Document>) => {
      // Price imputation: use area_m2 × PRICE_PER_SQM when price_total is missing
      const hasPrice = typeof l.price_total === 'number' && (l.price_total as number) > 0;
      const price_is_estimated = !hasPrice && typeof l.area_m2 === 'number' && (l.area_m2 as number) > 0;
      const price_total = hasPrice
        ? (l.price_total as number)
        : price_is_estimated
          ? Math.round((l.area_m2 as number) * PRICE_PER_SQM)
          : null;

      // Geocoded listings keep their real coords; un-geocoded ones fall back
      // to their Bezirk centroid tagged coordinate_source:'district' so they
      // still appear on the map (approximate). Only listings with no bezirk
      // at all stay 'none' / null and are hidden.
      const storedCoords = (l.coordinates as { lat: number; lon: number } | null | undefined) ?? null;
      const coordinates = resolveCoordinates(storedCoords, l.bezirk as string | null | undefined);
      const COORD_SOURCES = new Set(['exact', 'landmark', 'district', 'none']);
      const rawSource = (l.coordinate_source as string) || 'none';
      const coordinate_source: 'exact' | 'landmark' | 'district' | 'none' = !coordinates
        ? 'none'
        : !storedCoords
          ? 'district'
          : COORD_SOURCES.has(rawSource) && rawSource !== 'none'
            ? (rawSource as 'exact' | 'landmark' | 'district')
            : 'exact';

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
        image_url: l.image_url || null,
        coordinates: coordinates ?? null,
        coordinate_source,
        landmark_hint: l.landmark_hint || null,
        price_is_estimated,
        estimated_down_pct: l.estimated_down_pct ?? undefined,
        estimated_down_pct_kimv: l.estimated_down_pct_kimv ?? undefined,
        estimated_equity_eur: l.estimated_equity_eur ?? undefined,
        bank_score_confidence: l.bank_score_confidence ?? undefined,
        price_vs_avg_pct: priceVsAvgPct,
        ubahn_walk_minutes: typeof l.ubahn_walk_minutes === 'number' ? l.ubahn_walk_minutes : null,
        is_genossenschaft: l.is_genossenschaft === true,
      };
    });

    const finalResult = minScore > 0
      ? result.filter((l) => l.score == null || l.score >= minScore)
      : result;

    return NextResponse.json({ listings: finalResult, total: finalResult.length });
  } catch (err) {
    console.error('[/api/listings/map]', err);
    return NextResponse.json({ error: 'Database error' }, { status: 500 });
  }
}
