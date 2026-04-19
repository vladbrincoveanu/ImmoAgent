import type { MapListing, CoordinateSource } from './types';

// Type tests for MapListing and CoordinateSource

// Test that CoordinateSource is a union type of exactly 'exact' | 'landmark' | 'none'
const validSources: CoordinateSource[] = ['exact', 'landmark', 'none'];
const _sourceCheck: typeof validSources[number] = 'exact'; // Ensure it's a literal type

// Test that MapListing has all required fields
function assertMapListingShape(listing: MapListing): void {
  // Required fields
  const _id: string = listing._id;
  const _title: string | null = listing.title;
  const _url: string = listing.url;
  const _sourceEnum: string = listing.source_enum;
  const _bezirk: string | null = listing.bezirk;
  const _priceTotal: number | null = listing.price_total;
  const _areaM2: number | null = listing.area_m2;
  const _rooms: number | null = listing.rooms;
  const _score: number | null = listing.score;
  const _imageUrl: string | null = listing.image_url;
  const _coordinates: { lat: number; lon: number } | null = listing.coordinates;
  const _coordinateSource: CoordinateSource = listing.coordinate_source;
  const _landmarkHint: string | null = listing.landmark_hint;
}

// Test that MapListing coordinates can be accessed correctly
function testCoordinates(listing: MapListing): void {
  if (listing.coordinates) {
    const lat: number = listing.coordinates.lat;
    const lon: number = listing.coordinates.lon;
    console.log(lat, lon);
  }
}

// Test that coordinate_source is typed correctly
function testCoordinateSource(source: CoordinateSource): void {
  switch (source) {
    case 'exact':
      console.log('Exact coordinates');
      break;
    case 'landmark':
      console.log('Landmark-based coordinates');
      break;
    case 'none':
      console.log('No coordinates');
      break;
  }
}
