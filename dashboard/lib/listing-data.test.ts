import { describe, expect, it } from '@jest/globals';
import {
  MAP_PROJECTION,
  TOP_PROJECTION,
  buildListingSort,
  presentMapListing,
} from './listing-data';

const doc = {
  _id: { toString: () => '507f1f77bcf86cd799439011' },
  title: 'Test flat',
  url: 'https://example.test/listing',
  source_enum: 'willhaben',
  bezirk: '1010',
  price_total: 420000,
  area_m2: 60,
  rooms: 2,
  score: 72,
  scores: { default: 72, urban_professional: 81 },
  coordinates: null,
  coordinate_source: 'none',
};

describe('listing-data contracts', () => {
  it('projects only fields needed by each list surface', () => {
    expect(MAP_PROJECTION.title).toBe(1);
    expect(TOP_PROJECTION.processed_at).toBe(1);
    expect(MAP_PROJECTION.structured_analysis).toBeUndefined();
  });

  it('sorts profile scores without changing sort option names', () => {
    expect(buildListingSort('urban_professional', 'score_desc')).toEqual({
      'scores.urban_professional': -1,
      processed_at: -1,
    });
  });

  it('preserves district-centroid fallback and profile score', () => {
    const result = presentMapListing(doc, {
      profile: 'urban_professional',
      pricePerSqm: 7000,
      zoneAverage: 400000,
    });

    expect(result.score).toBe(81);
    expect(result.coordinates).not.toBeNull();
    expect(result.coordinate_source).toBe('district');
    expect(result.price_vs_avg_pct).toBe(5);
  });
});
