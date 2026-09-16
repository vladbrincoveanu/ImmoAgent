import { beforeEach, describe, expect, it, jest } from '@jest/globals';
import type { NextRequest } from 'next/server';
import { coopBaseQuery } from '@/lib/coop-query';

const mockFind = jest.fn();
const mockAggregate = jest.fn();
const mockCollection = {
  find: mockFind,
  aggregate: mockAggregate,
};
const mockDb = {
  collection: jest.fn(() => mockCollection),
};
const mockGetDb = jest.fn();

jest.mock('@/lib/mongodb', () => ({
  getDb: mockGetDb,
}), { virtual: true });

import { GET as getTop } from './route';

function request(url: string): NextRequest {
  return new Request(url) as unknown as NextRequest;
}

function queryFromFind(): Record<string, unknown> {
  return mockFind.mock.calls[0][0] as Record<string, unknown>;
}

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

import { GET as getMap } from '../map/route';

function conditionsFor(url: string, handler: (request: NextRequest) => Promise<Response>) {
  return handler(request(url)).then(async (response) => {
    expect(response.status).toBe(200);
    await response.json();
    const query = mockFind.mock.calls.at(-1)?.[0] as Record<string, unknown> | undefined;
    return query?.$and as Array<Record<string, unknown>>;
  });
}

beforeEach(() => {
  jest.clearAllMocks();
  mockGetDb.mockReturnValue(mockDb);
  mockFind.mockReturnValue({
    sort: () => ({
      limit: () => ({
        toArray: async () => [],
      }),
    }),
  });
  mockAggregate.mockReturnValue({ toArray: async () => [] });
});

describe('GET /api/listings/top', () => {
  it('excludes co-op rows from the default purchase feed', async () => {
    const response = await getTop(request('http://localhost/api/listings/top'));

    expect(response.status).toBe(200);
    expect(queryFromFind().$and).toContainEqual({ is_genossenschaft: { $ne: true } });
  });

  it('uses the co-op query instead of purchase price-per-area gates', async () => {
    const response = await getTop(request('http://localhost/api/listings/top?genossenschaft=true'));

    const conditions = queryFromFind().$and as Array<Record<string, unknown>>;
    expect(response.status).toBe(200);
    expect(conditions).toContainEqual(coopBaseQuery());
    expect(conditions.some((condition) => '$expr' in condition)).toBe(false);
  });

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
