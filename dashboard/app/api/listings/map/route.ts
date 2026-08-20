import { NextRequest, NextResponse } from 'next/server';
import { getDb } from '@/lib/mongodb';
import { Document } from 'mongodb';
import { validateDistrict, validateSort, validateMinScore, validateLimit } from '@/lib/validators';
import { DEFAULT_PROFILE, isValidProfile } from '@/lib/profile';
import { coopBaseQuery } from '@/lib/coop-query';
import { MAP_PROJECTION, buildListingSort, presentMapListing } from '@/lib/listing-data';
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

  // Co-op rentals carry no score, so score_desc — which the map page always
  // sends as its default — would order them arbitrarily. Newest-first instead;
  // any other explicitly chosen sort (price, area, date) still applies.
  const sortBy = buildListingSort(profile, sort, genossenschaft ? 'coop' : 'purchase');

  try {
    const db = getDb();
    if (!db) {
      return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });
    }
    if (district === null && searchParams.get('district') !== null) {
      console.warn('[/api/listings/map] Invalid district rejected:', searchParams.get('district'));
    }
    // Co-op rentals store the MONTHLY RENT in price_total, so the purchase €/m²
    // band below (2500–20000) rejects every one of them (€700 / 60 m² ≈ €12).
    // They therefore get their own gates — the shared /coop definition, which
    // already carries the Wien + livable-area guards — and the purchase map
    // excludes them explicitly rather than relying on that band to do it.
    const filter: Record<string, unknown> = genossenschaft
      ? {
          $and: [
            coopBaseQuery(),
            { listing_status: { $ne: 'taken' } },
            { price_total: { $gt: 0 } },
            { title: { $nin: [null, ''] } },
          ],
        }
      : {
          $and: [
            { url_is_valid: { $ne: false } },
            { listing_status: { $ne: "taken" } },
            { is_genossenschaft: { $ne: true } },
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


    const listings = await db
      .collection<Document>('listings')
      .find(filter, { projection: MAP_PROJECTION })
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

    const result = listings.map((l) => presentMapListing(l, {
      profile,
      pricePerSqm: PRICE_PER_SQM,
      zoneAverage: l.is_genossenschaft === true
        ? undefined
        : typeof l.bezirk === 'string'
          ? zoneAvgMap[l.bezirk]
          : undefined,
    }));

    const finalResult = minScore > 0
      ? result.filter((l) => l.score == null || l.score >= minScore)
      : result;

    return NextResponse.json({ listings: finalResult, total: finalResult.length }, {
      headers: { 'Cache-Control': 'public, max-age=15, s-maxage=15, stale-while-revalidate=60' },
    });
  } catch (err) {
    console.error('[/api/listings/map]', err);
    return NextResponse.json({ error: 'Database error' }, { status: 500 });
  }
}
