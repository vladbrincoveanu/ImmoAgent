export const dynamic = 'force-dynamic';

export async function GET() {
  return NextResponse.json({
    destinations: [
      { name: 'Stephansplatz (city center)', lat: 48.2082, lon: 16.3738, category: 'landmark' },
      { name: 'Karlsplatz', lat: 48.2019, lon: 16.3695, category: 'landmark' },
      { name: 'Hauptbahnhof (main station)', lat: 48.1858, lon: 16.3755, category: 'transit' },
      { name: 'Westbahnhof', lat: 48.1967, lon: 16.3400, category: 'transit' },
      { name: 'Praterstern', lat: 48.2178, lon: 16.3917, category: 'transit' },
      { name: 'Schwedenplatz', lat: 48.2113, lon: 16.3778, category: 'landmark' },
      { name: 'Donauinsel', lat: 48.2392, lon: 16.4089, category: 'recreation' },
      { name: 'Schönbrunn Palace', lat: 48.1849, lon: 16.3120, category: 'landmark' },
      { name: 'Wien Mitte (Landstraße)', lat: 48.2075, lon: 16.3833, category: 'transit' },
      { name: 'Wien Hütteldorf', lat: 48.1971, lon: 16.2605, category: 'transit' },
    ],
  });
}

import { NextResponse } from 'next/server';
