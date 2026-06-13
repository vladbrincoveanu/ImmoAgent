import { NextRequest, NextResponse } from 'next/server';
import { getDb, ObjectId } from '@/lib/mongodb';

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const db = getDb();
  if (!db) return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });

  const { id } = await params;

  try {
    const listing = await db.collection('listings').findOne(
      { _id: new ObjectId(id), listing_status: 'taken' },
      { projection: { title: 1, url: 1, price_history: 1, price_at_scrape: 1, price_total: 1 } }
    );

    if (!listing) {
      return NextResponse.json({ error: 'Listing not found' }, { status: 404 });
    }

    return NextResponse.json({
      _id: listing._id.toString(),
      title: listing.title,
      url: listing.url,
      price_history: listing.price_history || [],
      price_at_scrape: listing.price_at_scrape,
      price_total: listing.price_total
    });
  } catch (err) {
    console.error('[/api/listings/[id]/taken-detail]', err);
    return NextResponse.json({ error: 'Database error' }, { status: 500 });
  }
}