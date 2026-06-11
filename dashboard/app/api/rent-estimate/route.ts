import { NextRequest, NextResponse } from 'next/server';
import { getDb } from '@/lib/mongodb';

export const dynamic = 'force-dynamic';

// Average rent per m² in Vienna (€/month) by district. Source: Vienna rental market
// benchmarks. Outer districts are cheaper, central 1st district is highest.
const RENT_PER_M2: Record<string, number> = {
  '1010': 26, '1020': 20, '1030': 19, '1040': 19, '1050': 18, '1060': 18, '1070': 19,
  '1080': 19, '1090': 20, '1100': 16, '1110': 14, '1120': 15, '1130': 17, '1140': 15,
  '1150': 15, '1160': 15, '1170': 16, '1180': 17, '1190': 17, '1200': 16, '1210': 13,
  '1220': 13, '1230': 12,
};
const DEFAULT_RENT_PER_M2 = 15;

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const id = searchParams.get('id');
  const area = Number(searchParams.get('area_m2') ?? 0);
  const price = Number(searchParams.get('price_total') ?? 0);
  const bezirk = searchParams.get('bezirk');

  // Compute for a single listing by id
  const db = getDb();
  if (id) {
    if (!db) return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });
    let oid: import('mongodb').ObjectId;
    try { oid = new (await import('mongodb')).ObjectId(id); }
    catch { return NextResponse.json({ error: 'Invalid id' }, { status: 400 }); }
    const listing = await db.collection('listings').findOne({ _id: oid }, { projection: { area_m2: 1, price_total: 1, bezirk: 1, rooms: 1 } });
    if (!listing) return NextResponse.json({ error: 'Not found' }, { status: 404 });
    return NextResponse.json(estimate(listing.area_m2 as number, listing.price_total as number, listing.bezirk as string, listing.rooms as number));
  }

  if (!area || !price) {
    return NextResponse.json({ error: 'Missing area_m2 or price_total' }, { status: 400 });
  }
  return NextResponse.json(estimate(area, price, bezirk, null));
}

function estimate(area: number, price: number, bezirk: string | null, rooms: number | null) {
  if (!area || !price) {
    return { monthly_rent_eur: null, annual_rent_eur: null, gross_yield_pct: null, net_yield_pct: null, rent_per_m2: null };
  }
  const rpm2 = (bezirk && RENT_PER_M2[bezirk]) || DEFAULT_RENT_PER_M2;
  const monthly = Math.round(area * rpm2);
  const annual = monthly * 12;
  const gross = (annual / price) * 100;
  // Net yield subtracts ~30% for vacancy, maintenance, management
  const net = gross * 0.7;
  return {
    monthly_rent_eur: monthly,
    annual_rent_eur: annual,
    gross_yield_pct: Math.round(gross * 10) / 10,
    net_yield_pct: Math.round(net * 10) / 10,
    rent_per_m2: rpm2,
    is_above_market: gross < 3.5,
  };
}
