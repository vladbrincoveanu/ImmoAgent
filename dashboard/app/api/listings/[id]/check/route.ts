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
    const listing = await getDb().collection('listings').findOne({
      _id: new ObjectId(params.id),
    });

    if (!listing) {
      return NextResponse.json({ error: 'Not found' }, { status: 404 });
    }

    const isValid = await checkUrl(listing.url);

    await getDb().collection('listings').updateOne(
      { _id: new ObjectId(params.id) },
      { $set: { url_is_valid: isValid } }
    );

    return NextResponse.json({ url_is_valid: isValid });
  } catch (err) {
    console.error('[/api/listings/[id]/check]', err);
    return NextResponse.json({ error: 'Check failed' }, { status: 500 });
  }
}