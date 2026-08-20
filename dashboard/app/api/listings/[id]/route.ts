import { NextRequest, NextResponse } from 'next/server';
import { getDb, ObjectId } from '@/lib/mongodb';
import { validateObjectId } from '@/lib/validators';
import { DEFAULT_PROFILE, isValidProfile } from '@/lib/profile';
import { presentListingDetail } from '@/lib/listing-data';

export async function GET(
  req: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const validId = validateObjectId(id);
  if (!validId) {
    return NextResponse.json({ error: 'Invalid listing ID', field: 'id' }, { status: 400 });
  }

  try {
    const db = getDb();
    if (!db) {
      return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });
    }
    const listing = await db.collection('listings').findOne({
      _id: new ObjectId(validId),
    });

    if (!listing) {
      return NextResponse.json({ error: 'Not found' }, { status: 404 });
    }

    // Per-profile score override (?profile=...)
    const { searchParams } = new URL(req.url);
    const profileParam = searchParams.get('profile');
    const profile = isValidProfile(profileParam) ? (profileParam as string) : DEFAULT_PROFILE;
    const result = presentListingDetail(listing, { profile });

    return NextResponse.json(result, {
      headers: { 'Cache-Control': 'public, max-age=15, s-maxage=15, stale-while-revalidate=60' },
    });
  } catch (err) {
    console.error('[/api/listings/[id]]', err);
    return NextResponse.json({ error: 'Database error' }, { status: 500 });
  }
}
