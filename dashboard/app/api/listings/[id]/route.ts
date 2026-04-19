import { NextRequest, NextResponse } from 'next/server';
import { getDb, ObjectId } from '@/lib/mongodb';

export async function GET(
  _req: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const listing = await getDb().collection('listings').findOne({
      _id: new ObjectId(params.id),
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