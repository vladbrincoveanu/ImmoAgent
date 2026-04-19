import { NextRequest, NextResponse } from 'next/server';
import { db, ObjectId } from '@/lib/mongodb';

const SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000;

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const limit = Math.min(parseInt(searchParams.get('limit') || '20'), 100);
  const minScore = parseFloat(searchParams.get('min_score') || '0');
  const district = searchParams.get('district');

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

    const listings = await db
      .collection('listings')
      .find(filter)
      .sort({ score: -1, processed_at: -1 })
      .limit(limit)
      .toArray();

    const result = listings.map((l) => ({
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