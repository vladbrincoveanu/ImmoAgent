import { NextRequest, NextResponse } from 'next/server';
import { getDb, ObjectId } from '@/lib/mongodb';
import { validateObjectId } from '@/lib/validators';

export async function GET(
  _req: NextRequest,
  { params }: { params: { id: string } }
) {
  const validId = validateObjectId(params.id);
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

    return NextResponse.json(result);
  } catch (err) {
    console.error('[/api/listings/[id]]', err);
    return NextResponse.json({ error: 'Database error' }, { status: 500 });
  }
}