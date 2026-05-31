import { NextRequest, NextResponse } from 'next/server';
import { getDb } from '@/lib/mongodb';
import { Document, WithId } from 'mongodb';
import { validateDistrict, validateSort, validateMinScore, validateLimit, validateStatus } from '@/lib/validators';
// eslint-disable-next-line @typescript-eslint/no-require-imports
const config = require('../../../../config.json');

type ListingDocument = Document;



export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const limit = validateLimit(searchParams.get('limit'), 100);
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
      console.warn('[/api/listings/top] Invalid district rejected:', searchParams.get('district'));
    }
    const filter: Record<string, unknown> = {};

    const andConditions: Record<string, unknown>[] = [
      { $and: [
        { url_is_valid: { $ne: false } },
        { listing_status: { $ne: "taken" } },
        { price_total: { $gt: 0 } },
        { area_m2: { $gt: 0 } },
        { $expr: { $gte: [{ $divide: ["$price_total", "$area_m2"] }, 2500] } },
        { $expr: { $lte: [{ $divide: ["$price_total", "$area_m2"] }, 20000] } },
        { title: { $nin: [null, ""] } },
      ]},
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

    filter.$and = andConditions;

    const listings = await db
      .collection<ListingDocument>('listings')
      .find(filter)
      .sort(sortBy)
      .limit(limit)
      .toArray();

    const PRICE_PER_SQM = (config?.PRICE_PER_SQM as number | undefined) ?? 7000;

    const result = listings.map((l: WithId<ListingDocument>) => {
      const hasPrice = typeof l.price_total === 'number' && l.price_total > 0;
      const price_is_estimated = !hasPrice && typeof l.area_m2 === 'number' && l.area_m2 > 0;
      const price_total = hasPrice
        ? l.price_total
        : price_is_estimated
          ? Math.round(l.area_m2 * PRICE_PER_SQM)
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
        score: l.score,
        processed_at: l.processed_at,
        image_url: l.image_url || l.minio_image_path || null,
        url_is_valid: l.url_is_valid !== false,
        price_is_estimated,
        estimated_down_pct: l.estimated_down_pct ?? undefined,
        estimated_down_pct_kimv: l.estimated_down_pct_kimv ?? undefined,
        estimated_equity_eur: l.estimated_equity_eur ?? undefined,
        bank_score_confidence: l.bank_score_confidence ?? undefined,
      };
    });

    return NextResponse.json({ listings: result, total: result.length });
  } catch (err) {
    console.error('[/api/listings/top]', err);
    return NextResponse.json({ error: 'Database error' }, { status: 500 });
  }
}