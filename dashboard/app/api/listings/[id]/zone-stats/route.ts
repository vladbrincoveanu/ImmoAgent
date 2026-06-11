import { NextRequest, NextResponse } from 'next/server';
import { getDb, ObjectId } from '@/lib/mongodb';

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
  if (!listing.bezirk) return NextResponse.json({ error: 'No district' }, { status: 422 });

  const district = listing.bezirk;
  const price = listing.price_total;
  const area = listing.area_m2;

  const districtStats = await db.collection('listings').aggregate([
    {
      $match: {
        bezirk: district,
        url_is_valid: { $ne: false },
        listing_status: { $ne: 'taken' },
        price_total: { $gt: 0 },
        area_m2: { $gt: 0 },
      },
    },
    {
      $group: {
        _id: null,
        count: { $sum: 1 },
        avg_price: { $avg: '$price_total' },
        avg_price_per_m2: { $avg: { $divide: ['$price_total', '$area_m2'] } },
        min_price: { $min: '$price_total' },
        max_price: { $max: '$price_total' },
        avg_area: { $avg: '$area_m2' },
        avg_rooms: { $avg: '$rooms' },
      },
    },
  ]).toArray();

  const budgetMatchCount = await db.collection('listings').countDocuments({
    bezirk: district,
    url_is_valid: { $ne: false },
    listing_status: { $ne: 'taken' },
    price_total: { $gt: 0, $lte: 500000 },
    area_m2: { $gt: 0 },
  });

  const infraNearby = await db.collection('listings').aggregate([
    { $match: { bezirk: district, ubahn_walk_minutes: { $ne: null } } },
    { $group: { _id: null, avg_ubahn_min: { $avg: '$ubahn_walk_minutes' }, avg_school_min: { $avg: '$school_walk_minutes' } } },
  ]).toArray();

  const ds = districtStats[0] ?? { count: 0, avg_price: null, avg_price_per_m2: null, min_price: null, max_price: null, avg_area: null, avg_rooms: null };
  const infra = infraNearby[0] ?? {};

  let priceVsAvg: number | null = null;
  let pricePerM2VsAvg: number | null = null;
  if (price && area && ds.avg_price) {
    priceVsAvg = Math.round(((price - ds.avg_price) / ds.avg_price) * 100);
  }
  if (price && area && ds.avg_price_per_m2) {
    pricePerM2VsAvg = Math.round(((price / area - ds.avg_price_per_m2) / ds.avg_price_per_m2) * 100);
  }

  return NextResponse.json({
    district,
    total_in_district: ds.count,
    avg_price: ds.avg_price ? Math.round(ds.avg_price) : null,
    avg_price_per_m2: ds.avg_price_per_m2 ? Math.round(ds.avg_price_per_m2) : null,
    min_price: ds.min_price,
    max_price: ds.max_price,
    avg_area: ds.avg_area ? Math.round(ds.avg_area * 10) / 10 : null,
    avg_rooms: ds.avg_rooms ? Math.round(ds.avg_rooms * 10) / 10 : null,
    this_listing: {
      price,
      price_per_m2: price && area ? Math.round(price / area) : null,
      price_vs_avg_pct: priceVsAvg,
      price_per_m2_vs_avg_pct: pricePerM2VsAvg,
    },
    matching_budget: budgetMatchCount,
    avg_ubahn_minutes: infra.avg_ubahn_min ? Math.round(infra.avg_ubahn_min * 10) / 10 : null,
    avg_school_minutes: infra.avg_school_min ? Math.round(infra.avg_school_min * 10) / 10 : null,
  });
}
