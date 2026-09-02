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

import { GET } from './route';

function request(url: string): NextRequest {
  return new Request(url) as unknown as NextRequest;
}

function queryFromFind(): Record<string, unknown> {
  return mockFind.mock.calls[0][0] as Record<string, unknown>;
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
    const response = await GET(request('http://localhost/api/listings/top'));

    expect(response.status).toBe(200);
    expect(queryFromFind().$and).toContainEqual({ is_genossenschaft: { $ne: true } });
  });

  it('uses the co-op query instead of purchase price-per-area gates', async () => {
    const response = await GET(request('http://localhost/api/listings/top?genossenschaft=true'));

    const conditions = queryFromFind().$and as Array<Record<string, unknown>>;
    expect(response.status).toBe(200);
    expect(conditions).toContainEqual(coopBaseQuery());
    expect(conditions.some((condition) => '$expr' in condition)).toBe(false);
  });
});
