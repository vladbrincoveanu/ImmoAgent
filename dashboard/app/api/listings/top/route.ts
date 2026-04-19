import { NextRequest, NextResponse } from 'next/server';
import { getDb } from '@/lib/mongodb';
import { Document, WithId } from 'mongodb';

type ListingDocument = Document;

const SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000;

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const limit = Math.min(parseInt(searchParams.get('limit') || '20'), 100);
  const minScore = parseFloat(searchParams.get('min_score') || '0');
  const district = searchParams.get('district');
  const sort = searchParams.get('sort') || 'score_desc';

  const sortOptions: Record<string, Record<string, 1 | -1>> = {
    score_desc: { score: -1, processed_at: -1 },
    price_asc: { price_total: 1 },
    price_desc: { price_total: -1 },
    date_desc: { processed_at: -1 },
    area_desc: { area_m2: -1 },
  };
  const sortBy = sortOptions[sort] ?? sortOptions.score_desc;

  try {
    const cutoff = Date.now() - SEVEN_DAYS_MS;

    const filter: Record<string, unknown> = {
      processed_at: { $gte: cutoff / 1000 },
    };

    if (minScore > 0) {
      filter.$or = [
        { score: { $gte: minScore } },
        { score: null },
      ];
    }

    if (district) {
      filter.bezirk = district;
    }

    const listings = await getDb()
      .collection<ListingDocument>('listings')
      .find(filter)
      .sort(sortBy)
      .limit(limit)
      .toArray();

    const result = listings.map((l: WithId<ListingDocument>) => ({
      _id: l._id.toString(),
      title: l.title,
      url: l.url,
      source_enum: l.source_enum,
      bezirk: l.bezirk,
      price_total: l.price_total,
      area_m2: l.area_m2,
      rooms: l.rooms,
      score: l.score,
      processed_at: l.processed_at,
      image_url: l.image_url || l.minio_image_path || null,
      url_is_valid: l.url_is_valid !== false,
    }));

    return NextResponse.json({ listings: result, total: result.length });
  } catch (err) {
    console.error('[/api/listings/top]', err);
    return NextResponse.json({ error: 'Database error' }, { status: 500 });
  }
}