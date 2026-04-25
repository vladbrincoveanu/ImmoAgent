import { NextRequest, NextResponse } from 'next/server';
import { getDb } from '@/lib/mongodb';
import { MapListing } from '@/lib/types';
import { Document, WithId } from 'mongodb';
import { validateDistrict, validateSort, validateMinScore, validateLimit } from '@/lib/validators';
// eslint-disable-next-line @typescript-eslint/no-require-imports
const config = require('../../../../config.json');

// Vienna district centroid coordinates (approximate lat/lon for each district)
const DISTRICT_CENTROIDS: Record<string, { lat: number; lon: number }> = {
  '1010': { lat: 48.2082, lon: 16.3716 },
  '1020': { lat: 48.2126, lon: 16.3899 },
  '1030': { lat: 48.2089, lon: 16.3965 },
  '1040': { lat: 48.1984, lon: 16.3850 },
  '1050': { lat: 48.1923, lon: 16.3795 },
  '1060': { lat: 48.1973, lon: 16.3670 },
  '1070': { lat: 48.1991, lon: 16.3538 },
  '1080': { lat: 48.2016, lon: 16.3462 },
  '1090': { lat: 48.2165, lon: 16.3578 },
  '1100': { lat: 48.1856, lon: 16.3775 },
  '1110': { lat: 48.1714, lon: 16.4194 },
  '1120': { lat: 48.1901, lon: 16.3452 },
  '1130': { lat: 48.1939, lon: 16.2833 },
  '1140': { lat: 48.2090, lon: 16.3047 },
  '1150': { lat: 48.1975, lon: 16.3123 },
  '1160': { lat: 48.2135, lon: 16.3153 },
  '1170': { lat: 48.2236, lon: 16.3044 },
  '1180': { lat: 48.2256, lon: 16.2848 },
  '1190': { lat: 48.2359, lon: 16.3047 },
  '1200': { lat: 48.2352, lon: 16.3654 },
  '1210': { lat: 48.2446, lon: 16.3936 },
  '1220': { lat: 48.2427, lon: 16.4345 },
  '1230': { lat: 48.1508, lon: 16.3155 },
};

function getDistrictCentroid(bezirk: string | null): { lat: number; lon: number } | null {
  if (!bezirk) return null;
  return DISTRICT_CENTROIDS[bezirk] ?? null;
}

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const limit = validateLimit(searchParams.get('limit'), 200);
  const minScore = validateMinScore(searchParams.get('min_score'));
  const district = validateDistrict(searchParams.get('district'));
  const sort = validateSort(searchParams.get('sort'));

  const sortOptions: Record<string, Record<string, 1 | -1>> = {
    score_desc: { score: -1, processed_at: -1 },
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
    // Show ALL listings — those with coordinates use exact location, those without use district centroid fallback
    const filter: Record<string, unknown> = {};

    if (minScore > 0) {
      filter.score = { $gte: minScore };
    }

    if (district) {
      filter.bezirk = district;
    }

    const listings = await db
      .collection<Document>('listings')
      .find(filter)
      .sort(sortBy)
      .limit(limit)
      .toArray();

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

      // Use actual coordinates if available, otherwise fall back to district centroid
      let coordinates = l.coordinates as { lat: number; lon: number } | null | undefined;
      let coordinate_source: string = (l.coordinate_source as string) || 'none';

      if (!coordinates) {
        const centroid = getDistrictCentroid(l.bezirk as string | null);
        if (centroid) {
          coordinates = centroid;
          coordinate_source = 'district';
        }
      }

      return {
        _id: l._id.toString(),
        title: l.title,
        url: l.url,
        source_enum: l.source_enum,
        bezirk: l.bezirk,
        price_total,
        area_m2: l.area_m2,
        rooms: l.rooms,
        score: l.score,
        image_url: l.image_url || null,
        coordinates: coordinates ?? null,
        coordinate_source: coordinate_source as MapListing['coordinate_source'],
        landmark_hint: l.landmark_hint || null,
        price_is_estimated,
      };
    });

    return NextResponse.json({ listings: result, total: result.length });
  } catch (err) {
    console.error('[/api/listings/map]', err);
    return NextResponse.json({ error: 'Database error' }, { status: 500 });
  }
}
