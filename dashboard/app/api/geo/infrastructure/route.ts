import { NextRequest, NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';

const DATA_ROOT = path.join(process.cwd(), '..', 'Project', 'data');

async function loadJson<T>(filename: string): Promise<T> {
  const raw = await fs.readFile(path.join(DATA_ROOT, filename), 'utf-8');
  return JSON.parse(raw) as T;
}

interface UbahnEntry { name: string; lat: number; lon: number }
interface UbahnMap { [postal: string]: UbahnEntry[] }
interface SchoolEntry { name: string; type: string; lat: number; lon: number }

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const typesParam = searchParams.get('types') ?? 'ubahn,schools';
  const wanted = new Set(typesParam.split(',').map((s) => s.trim()));

  try {
    const [ubahn, schools] = await Promise.all([
      wanted.has('ubahn') ? loadJson<UbahnMap>('ubahn_coordinates.json') : Promise.resolve({} as UbahnMap),
      wanted.has('schools') ? loadJson<SchoolEntry[]>('vienna_schools.json') : Promise.resolve([] as SchoolEntry[]),
    ]);

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
