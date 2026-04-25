import { NextRequest, NextResponse } from 'next/server';
import { getDb, ObjectId } from '@/lib/mongodb';

async function checkUrl(url: string): Promise<boolean> {
  try {
    const res = await fetch(url, { method: 'HEAD', redirect: 'follow' });
    return res.ok;
  } catch {
    return false;
  }
}

export async function POST(
  _req: NextRequest,
  { params }: { params: { id: string } }
) {
  try {
    const db = getDb();
    if (!db) {
      return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });
    }
    const listing = await db.collection('listings').findOne({
      _id: new ObjectId(params.id),
    });

    if (!listing) {
      return NextResponse.json({ error: 'Not found' }, { status: 404 });
    }

    const isValid = await checkUrl(listing.url);

    await db.collection('listings').updateOne(
      { _id: new ObjectId(params.id) },
      { $set: { url_is_valid: isValid } }
    );

    return NextResponse.json({ url_is_valid: isValid });
  } catch (err) {
    console.error('[/api/listings/[id]/check]', err);
    return NextResponse.json({ error: 'Check failed' }, { status: 500 });
  }
}