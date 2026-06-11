import { NextRequest, NextResponse } from 'next/server';
import { getDb, ObjectId } from '@/lib/mongodb';

export const dynamic = 'force-dynamic';

export async function GET(
  _req: NextRequest,
  { params }: { params: { id: string } }
) {
  const db = getDb();
  if (!db) return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });

  let oid: ObjectId;
  try { oid = new ObjectId(params.id); }
  catch { return NextResponse.json({ error: 'Invalid listing ID' }, { status: 400 }); }

  const listing = await db.collection('listings').findOne({ _id: oid });
  if (!listing) return NextResponse.json({ error: 'Not found' }, { status: 404 });

  const { price_total, area_m2, bezirk, rooms, score } = listing as {
    price_total?: number; area_m2?: number; bezirk?: string; rooms?: number; score?: number;
  };

  if (!area_m2 || !price_total || !bezirk) {
    return NextResponse.json({ comparables: [] });
  }

  const areaLow = area_m2 * 0.75;
  const areaHigh = area_m2 * 1.4;
  const priceLow = price_total * 0.7;
  const priceHigh = price_total * 1.4;

  const candidates = await db.collection('listings').find({
    _id: { $ne: oid },
    url_is_valid: { $ne: false },
    listing_status: { $ne: 'taken' },
    bezirk,
    area_m2: { $gte: areaLow, $lte: areaHigh },
    price_total: { $gte: priceLow, $lte: priceHigh },
  }, {
    projection: {
      _id: 1, title: 1, url: 1, price_total: 1, area_m2: 1, rooms: 1,
      bezirk: 1, score: 1, image_url: 1, source_enum: 1,
    },
  }).limit(40).toArray();

  // Score the candidates: prefer same rooms, better score, lower price per m2
  const thisPpm2 = price_total / area_m2;
  const scored = candidates.map((c) => {
    const cPpm2 = (c.price_total as number) / (c.area_m2 as number);
    const roomMatch = rooms && c.rooms === rooms ? 0 : 1;
    const scoreDelta = ((c.score as number | null) ?? 0) - (score ?? 0);
    const ppm2Delta = (cPpm2 - thisPpm2) / thisPpm2;
    const rank = scoreDelta * 0.6 - ppm2Delta * 0.4 - roomMatch * 0.1;
    return { c, rank, cPpm2 };
  }).sort((a, b) => b.rank - a.rank);

  const top = scored.slice(0, 5).map(({ c, cPpm2 }) => ({
    _id: c._id.toString(),
    title: c.title,
    url: c.url,
    price_total: c.price_total,
    area_m2: c.area_m2,
    rooms: c.rooms,
    bezirk: c.bezirk,
    score: c.score,
    image_url: c.image_url,
    source_enum: c.source_enum,
    price_per_m2: Math.round(cPpm2),
    better_deal: cPpm2 < thisPpm2 && ((c.score as number | null) ?? 0) >= (score ?? 0),
    this_ppm2: Math.round(thisPpm2),
  }));

  return NextResponse.json({
    this_listing: { _id: params.id, price_total, area_m2, bezirk, score, price_per_m2: Math.round(thisPpm2) },
    comparables: top,
  });
}
