import { NextRequest, NextResponse } from 'next/server';
import { getDb } from '@/lib/mongodb';
import { MapListing } from '@/lib/types';
import { Document, WithId } from 'mongodb';

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const limit = Math.min(parseInt(searchParams.get('limit') || '50'), 200);
  const minScore = parseFloat(searchParams.get('min_score') || '0');
  const district = searchParams.get('district');

  try {
    // Show listings that have coordinates (exact/landmark) OR haven't been geocoded yet (no field).
    // Listings with coordinate_source='none' have no usable location and are excluded.
    const filter: Record<string, unknown> = {
      $or: [
        { coordinate_source: { $in: ['exact', 'landmark'] } },
        { coordinate_source: { $exists: false } },
      ],
    };

    if (minScore > 0) {
      filter.score = { $gte: minScore };
    }

    if (district) {
      filter.bezirk = district;
    }

    const listings = await getDb()
      .collection<Document>('listings')
      .find(filter)
      .sort({ score: -1 })
      .limit(limit)
      .toArray();

    const result: MapListing[] = listings.map((l: WithId<Document>) => ({
      _id: l._id.toString(),
      title: l.title,
      url: l.url,
      source_enum: l.source_enum,
      bezirk: l.bezirk,
      price_total: l.price_total,
      area_m2: l.area_m2,
      rooms: l.rooms,
      score: l.score,
      image_url: l.image_url || null,
      coordinates: l.coordinates || null,
      coordinate_source: l.coordinate_source || 'none',
      landmark_hint: l.landmark_hint || null,
    }));

    return NextResponse.json({ listings: result, total: result.length });
  } catch (err) {
    console.error('[/api/listings/map]', err);
    return NextResponse.json({ error: 'Database error' }, { status: 500 });
  }
}
