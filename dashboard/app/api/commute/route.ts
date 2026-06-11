import { NextRequest, NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';

export const dynamic = 'force-dynamic';

const DATA_ROOT = path.join(process.cwd(), '..', 'Project', 'data');

interface UbahnEntry { name: string; lat: number; lon: number }
interface UbahnMap { [postal: string]: UbahnEntry[] }

const HAVERSINE_KMH = 111.195; // km per degree latitude
const WALK_KMH = 4.8; // ~80m/min
const TRAIN_KMH = 30; // average U-Bahn including stops

function haversineKm(a: { lat: number; lon: number }, b: { lat: number; lon: number }): number {
  const R = 6371;
  const dLat = (b.lat - a.lat) * Math.PI / 180;
  const dLon = (b.lon - a.lon) * Math.PI / 180;
  const lat1 = a.lat * Math.PI / 180;
  const lat2 = b.lat * Math.PI / 180;
  const x = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(x));
}

let ubahnCache: UbahnMap | null = null;
let ubahnListCache: Array<{ name: string; lat: number; lon: number; postal: string }> | null = null;

async function loadUbahn(): Promise<{ byPostal: UbahnMap; flat: Array<{ name: string; lat: number; lon: number; postal: string }> }> {
  if (ubahnCache && ubahnListCache) return { byPostal: ubahnCache, flat: ubahnListCache };
  const raw = await fs.readFile(path.join(DATA_ROOT, 'ubahn_coordinates.json'), 'utf-8');
  const data = JSON.parse(raw) as UbahnMap;
  ubahnCache = data;
  const flat: Array<{ name: string; lat: number; lon: number; postal: string }> = [];
  for (const [postal, stations] of Object.entries(data)) {
    for (const s of stations) flat.push({ name: s.name, lat: s.lat, lon: s.lon, postal });
  }
  ubahnListCache = flat;
  return { byPostal: data, flat };
}

export async function GET(request: NextRequest) {
  const { searchParams } = new URL(request.url);
  const listingLat = Number(searchParams.get('lat') ?? 0);
  const listingLon = Number(searchParams.get('lon') ?? 0);
  const destLat = Number(searchParams.get('dest_lat') ?? 0);
  const destLon = Number(searchParams.get('dest_lon') ?? 0);
  const destName = searchParams.get('dest_name') ?? 'Destination';

  if (!listingLat || !listingLon || !destLat || !destLon) {
    return NextResponse.json({ error: 'Missing lat/lon for listing or destination' }, { status: 400 });
  }

  try {
    const { flat } = await loadUbahn();
    const listing = { lat: listingLat, lon: listingLon };
    const destination = { lat: destLat, lon: destLon };

    // Find nearest U-Bahn to listing
    let nearestToListing: typeof flat[0] | null = null;
    let minListingDist = Infinity;
    for (const s of flat) {
      const d = haversineKm(listing, s);
      if (d < minListingDist) { minListingDist = d; nearestToListing = s; }
    }

    // Find nearest U-Bahn to destination
    let nearestToDest: typeof flat[0] | null = null;
    let minDestDist = Infinity;
    for (const s of flat) {
      const d = haversineKm(destination, s);
      if (d < minDestDist) { minDestDist = d; nearestToDest = s; }
    }

    // Walk-only option
    const walkOnlyKm = haversineKm(listing, destination);
    const walkOnlyMin = Math.round((walkOnlyKm / WALK_KMH) * 60);

    // Transit option
    let transitMin: number | null = null;
    let transitRoute: { from: string; to: string; transfer: string | null } | null = null;
    if (nearestToListing && nearestToDest) {
      const walkToStation = (minListingDist / WALK_KMH) * 60;
      const trainMin = (haversineKm(nearestToListing, nearestToDest) / TRAIN_KMH) * 60;
      const walkFromStation = (minDestDist / WALK_KMH) * 60;
      const transferMin = 4; // average transfer / wait
      transitMin = Math.round(walkToStation + trainMin + walkFromStation + transferMin);

      // If same station, no transfer needed
      const sameStation = nearestToListing.name === nearestToDest.name && nearestToListing.postal === nearestToDest.postal;
      transitMin = sameStation
        ? Math.round(walkToStation + trainMin + walkFromStation)
        : Math.round(walkToStation + trainMin + walkFromStation + transferMin);
      transitRoute = {
        from: nearestToListing.name,
        to: nearestToDest.name,
        transfer: sameStation ? null : 'Change at central',
      };
    }

    const recommendTransit = transitMin != null && transitMin < walkOnlyMin;
    const recommendedMin = recommendTransit ? transitMin : walkOnlyMin;
    const recommendedMode: 'transit' | 'walk' = recommendTransit ? 'transit' : 'walk';

    return NextResponse.json({
      destination: { name: destName, lat: destLat, lon: destLon },
      walk: { minutes: walkOnlyMin, km: Math.round(walkOnlyKm * 100) / 100 },
      transit: transitMin != null ? { minutes: transitMin, route: transitRoute } : null,
      recommended: { minutes: recommendedMin, mode: recommendedMode },
    }, { headers: { 'Cache-Control': 'public, max-age=300' } });
  } catch (err) {
    console.error('[/api/commute]', err);
    return NextResponse.json({ error: 'Failed to load transit data' }, { status: 500 });
  }
}
