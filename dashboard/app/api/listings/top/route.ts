import { NextRequest, NextResponse } from 'next/server';
import { getDb } from '@/lib/mongodb';
import { Document } from 'mongodb';
import { validateDistrict, validateSort, validateMinScore, validateLimit, validateStatus } from '@/lib/validators';
import { DEFAULT_PROFILE, isValidProfile } from '@/lib/profile';
import { TOP_PROJECTION, buildListingSort, presentTopListing } from '@/lib/listing-data';
// eslint-disable-next-line @typescript-eslint/no-require-imports
const config = require('../../../../config.json');

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const limit = validateLimit(searchParams.get('limit'), 100);
  const minScore = validateMinScore(searchParams.get('min_score'));
  const district = validateDistrict(searchParams.get('district'));
  const sort = validateSort(searchParams.get('sort'));
  const genossenschaft = searchParams.get('genossenschaft') === 'true';

  const profileParam = searchParams.get('profile');
  const profile = isValidProfile(profileParam) ? (profileParam as string) : DEFAULT_PROFILE;
  if (profileParam && !isValidProfile(profileParam)) {
    console.warn('[/api/listings/top] Invalid profile rejected:', profileParam);
  }

  const sortBy = buildListingSort(profile, sort, genossenschaft ? 'coop' : 'purchase');

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

    // min_score is applied AFTER mapping (below), on the profile-resolved
    // score the client actually displays — the raw `score` field can differ
    // from scores.<profile> and filtering on it lets mismatches leak through.

    if (district) {
      andConditions.push({ bezirk: district });
    }

    if (genossenschaft) {
      andConditions.push({ is_genossenschaft: true });
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
      .collection<Document>('listings')
      .find(filter, { projection: TOP_PROJECTION })
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

    const result = listings.map((l) => presentTopListing(l, {
      profile,
      pricePerSqm: PRICE_PER_SQM,
      zoneAverage: typeof l.bezirk === 'string' ? zoneAvgMap[l.bezirk] : undefined,
    }));

    let finalResult = belowAvgPct > 0
      ? result.filter((l) => l.price_vs_avg_pct != null && l.price_vs_avg_pct <= -belowAvgPct)
      : result;
    if (minScore > 0) {
      finalResult = finalResult.filter((l) => l.score == null || l.score >= minScore);
    }

    return NextResponse.json({ listings: finalResult, total: finalResult.length }, {
      headers: { 'Cache-Control': 'public, max-age=15, s-maxage=15, stale-while-revalidate=60' },
    });
  } catch (err) {
    console.error('[/api/listings/top]', err);
    return NextResponse.json({ error: 'Database error' }, { status: 500 });
  }
}
