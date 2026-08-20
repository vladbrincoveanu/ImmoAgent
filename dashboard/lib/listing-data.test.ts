import { describe, expect, it } from '@jest/globals';
import {
  MAP_PROJECTION,
  TOP_PROJECTION,
  buildMapListingFilter,
  buildListingSort,
  buildTopListingFilter,
  presentMapListing,
  presentListingDetail,
  presentTopListing,
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

  it('preserves purchase and co-op filter predicates', () => {
    const purchase = buildMapListingFilter({ district: '1010', genossenschaft: false });
    expect(purchase.$and).toEqual(expect.arrayContaining([
      { is_genossenschaft: { $ne: true } },
    ]));
    expect(purchase.bezirk).toBe('1010');

    const coop = buildMapListingFilter({ district: null, genossenschaft: true });
    expect(coop.$and).toEqual(expect.arrayContaining([{ listing_status: { $ne: 'taken' } }]));
    expect(coop.$and?.[0]).toMatchObject({ is_genossenschaft: true });
  });

  it('preserves top status and below-average filter gates', () => {
    const filter = buildTopListingFilter({
      district: '1020',
      genossenschaft: true,
      status: 'taken',
      belowAvgPct: 10,
    });

    expect(filter.$and).toEqual(expect.arrayContaining([
      { bezirk: '1020' },
      { is_genossenschaft: true },
      { listing_status: 'taken' },
      { bezirk: { $exists: true, $ne: null } },
    ]));
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

  it('preserves top-list fields and image fallback', () => {
    const result = presentTopListing({
      ...doc,
      processed_at: 123,
      minio_image_path: 'https://cdn.example.test/image.jpg',
      url_is_valid: false,
      address: 'Test address',
      price_history: [{ price_total: 420000, date: 123 }],
    }, {
      profile: 'default',
      pricePerSqm: 7000,
      zoneAverage: 400000,
    });

    expect(result.processed_at).toBe(123);
    expect(result.image_url).toBe('https://cdn.example.test/image.jpg');
    expect(result.url_is_valid).toBe(false);
    expect(result.address).toBe('Test address');
    expect(result.price_history).toEqual([{ price_total: 420000, date: 123 }]);
  });

  it('keeps detail responses to the public listing contract', () => {
    const result = presentListingDetail({
      ...doc,
      secret_internal_note: 'do not expose',
    }, { profile: 'urban_professional' });

    expect(result.score).toBe(81);
    expect(result.profile).toBe('urban_professional');
    expect(result.coordinates).not.toBeNull();
    expect(result).not.toHaveProperty('secret_internal_note');
  });
});
