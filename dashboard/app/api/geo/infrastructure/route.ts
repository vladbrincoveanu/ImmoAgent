import { NextRequest, NextResponse } from 'next/server';
// Static imports so the data is bundled into the serverless function —
// reading ../Project/data off the filesystem does not exist on Vercel,
// where only dashboard/ is deployed.
import ubahnJson from '@/data/ubahn_coordinates.json';
import schoolsJson from '@/data/vienna_schools.json';

interface UbahnEntry { name: string; lat: number; lon: number }
interface UbahnMap { [postal: string]: UbahnEntry[] }
interface SchoolEntry { name: string; type: string; lat: number; lon: number }

const ubahn = ubahnJson as UbahnMap;
const schools = schoolsJson as SchoolEntry[];

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const typesParam = searchParams.get('types') ?? 'ubahn,schools';
    const wanted = new Set(typesParam.split(',').map((s) => s.trim()));

    const features: Array<{
      type: 'Feature';
      geometry: { type: 'Point'; coordinates: [number, number] };
      properties: { kind: 'ubahn' | 'school'; name: string; type?: string; district?: string };
    }> = [];

    if (wanted.has('ubahn')) {
      for (const [postal, stations] of Object.entries(ubahn)) {
        for (const s of stations) {
          features.push({
            type: 'Feature',
            geometry: { type: 'Point', coordinates: [s.lon, s.lat] },
            properties: { kind: 'ubahn', name: s.name, district: postal },
          });
        }
      }
    }
    if (wanted.has('schools')) {
      for (const s of schools) {
        features.push({
          type: 'Feature',
          geometry: { type: 'Point', coordinates: [s.lon, s.lat] },
          properties: { kind: 'school', name: s.name, type: s.type },
        });
      }
    }

    return NextResponse.json({ type: 'FeatureCollection', features }, {
      headers: { 'Cache-Control': 'public, max-age=3600' },
    });
  } catch (err) {
    console.error('[/api/geo/infrastructure]', err);
    return NextResponse.json({ error: 'Failed to load geo data' }, { status: 500 });
  }
}
