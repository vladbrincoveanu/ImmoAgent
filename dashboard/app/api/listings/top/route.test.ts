import { describe, expect, it, beforeEach, jest } from '@jest/globals';
import type { NextRequest } from 'next/server';

type Cursor = {
  sort: () => Cursor;
  limit: () => Cursor;
  toArray: () => Promise<unknown[]>;
};
type Collection = { find: (query: Record<string, unknown>) => Cursor };
type Db = { collection: () => Collection };

const mockGetDb = jest.fn<() => Db>();
const mockFind = jest.fn<(query: Record<string, unknown>) => Cursor>();
const mockCollection: Collection = { find: mockFind };
const mockDb: Db = { collection: jest.fn(() => mockCollection) };

jest.mock('@/lib/mongodb', () => ({ getDb: mockGetDb }), { virtual: true });
jest.mock('@/lib/validators', () => ({
  validateDistrict: () => null,
  validateSort: () => 'score_desc',
  validateMinScore: () => 0,
  validateLimit: (_value: string | null, fallback: number) => fallback,
  validateStatus: () => 'active',
}), { virtual: true });
jest.mock('@/lib/profile', () => ({
  DEFAULT_PROFILE: 'default',
  isValidProfile: () => false,
}), { virtual: true });
jest.mock('@/lib/district-centroids', () => ({
  resolveCoordinates: () => null,
}), { virtual: true });
jest.mock('@/lib/coop-query', () => ({
  coopBaseQuery: () => ({
    is_genossenschaft: true,
    url_is_valid: { $ne: false },
    listing_status: { $ne: 'taken' },
    coop_source: { $ne: 'willhaben' },
    buyable: false,
    bezirk: { $regex: '^1\\d{3}$' },
  }),
}), { virtual: true });
jest.mock('@/lib/purchase-listing-query', () => ({
  purchasePricePerSqmConditions: () => [
    { $expr: { $gte: [{ $divide: ['$price_total', '$area_m2'] }, 1000] } },
    { $expr: { $lte: [{ $divide: ['$price_total', '$area_m2'] }, 20000] } },
  ],
}), { virtual: true });

import { GET as getTop } from './route';
import { GET as getMap } from '../map/route';

function request(url: string): NextRequest {
  return { url } as NextRequest;
}

function conditionsFor(url: string, handler: (request: NextRequest) => Promise<Response>) {
  return handler(request(url)).then(async (response) => {
    expect(response.status).toBe(200);
    await response.json();
    const query = mockFind.mock.calls.at(-1)?.[0];
    return query?.$and as Array<Record<string, unknown>>;
  });
}

beforeEach(() => {
  jest.clearAllMocks();
  const cursor: Cursor = {
    sort: jest.fn<() => Cursor>().mockReturnThis(),
    limit: jest.fn<() => Cursor>().mockReturnThis(),
    toArray: jest.fn<() => Promise<unknown[]>>().mockResolvedValue([]),
  };
  mockFind.mockReturnValue(cursor);
  mockGetDb.mockReturnValue(mockDb);
});

describe('listing route query modes', () => {
  it.each([
    ['top', getTop],
    ['map', getMap],
  ])('uses the rental co-op query without purchase sqm gates for %s', async (_name, handler) => {
    const conditions = await conditionsFor(
      'http://localhost/api/listings?genossenschaft=true', handler);

    expect(conditions).toEqual(expect.arrayContaining([
      expect.objectContaining({ is_genossenschaft: true }),
    ]));
    expect(conditions.some((condition) => '$expr' in condition)).toBe(false);
  });

  it.each([
    ['top', getTop],
    ['map', getMap],
  ])('keeps co-ops out of the purchase query for %s', async (_name, handler) => {
    const conditions = await conditionsFor(
      'http://localhost/api/listings', handler);

    expect(conditions).toEqual(expect.arrayContaining([
      expect.objectContaining({ is_genossenschaft: { $ne: true } }),
    ]));
    expect(conditions.some((condition) => '$expr' in condition)).toBe(true);
  });
});
