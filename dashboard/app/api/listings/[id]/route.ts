import { NextRequest, NextResponse } from 'next/server';
import { getDb, ObjectId } from '@/lib/mongodb';
import { validateObjectId } from '@/lib/validators';
import { DEFAULT_PROFILE, isValidProfile } from '@/lib/profile';
import { resolveCoordinates } from '@/lib/district-centroids';

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
    const scores = (listing as { scores?: Record<string, number | null> }).scores;
    const profileScore = (scores?.[profile] ?? listing.score ?? null) as number | null;

    // Flatten for response
    const result: Record<string, unknown> = { _id: listing._id.toString() };
    for (const [key, value] of Object.entries(listing)) {
      if (key === '_id') continue;
      if (value instanceof ObjectId) {
        result[key] = value.toString();
      } else {
        result[key] = value;
      }
    }
    // Override the score field to reflect the active profile
    result['score'] = profileScore;
    result['profile'] = profile;
    // Add resolved coordinates (stored or district centroid fallback)
    result['coordinates'] = resolveCoordinates(
      (listing as { coordinates?: { lat: number; lon: number } | null }).coordinates ?? null,
      (listing as { bezirk?: string }).bezirk
    );

    return NextResponse.json(result);
  } catch (err) {
    console.error('[/api/listings/[id]]', err);
    return NextResponse.json({ error: 'Database error' }, { status: 500 });
  }
}