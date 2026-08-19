import { beforeEach, describe, expect, it, jest } from '@jest/globals';
import { NextRequest } from 'next/server';
import { getDb } from '@/lib/mongodb';
import { GET as getMap } from './listings/map/route';
import { GET as getDetail } from './listings/[id]/route';

jest.mock('@/lib/mongodb', () => ({
  getDb: jest.fn(),
  ObjectId: class ObjectId {
    constructor(readonly value: string) {}

    toString() {
      return this.value;
    }
  },
}), { virtual: true });

jest.mock('@/lib/validators', () => ({
  validateDistrict: jest.fn(() => null),
  validateSort: jest.fn(() => 'score_desc'),
  validateMinScore: jest.fn(() => 0),
  validateLimit: jest.fn((_value: string | null, fallback: number) => fallback),
  validateObjectId: jest.fn((value: string) => value === 'bad' ? null : value),
}), { virtual: true });

jest.mock('@/lib/profile', () => ({
  DEFAULT_PROFILE: 'default',
  isValidProfile: jest.fn(() => false),
}), { virtual: true });

jest.mock('@/lib/district-centroids', () => ({
  resolveCoordinates: jest.fn(() => null),
}), { virtual: true });

jest.mock('@/lib/coop-query', () => ({
  coopBaseQuery: jest.fn(() => ({})),
}), { virtual: true });

const mockedGetDb = jest.mocked(getDb);

describe('public API status contracts', () => {
  beforeEach(() => {
    mockedGetDb.mockReset();
  });

  it('returns 503 when the map database is unavailable', async () => {
    mockedGetDb.mockReturnValue(null);

    const response = await getMap(new NextRequest('http://localhost/api/listings/map'));

    expect(response.status).toBe(503);
  });

  it('returns 400 before database access for an invalid detail id', async () => {
    const response = await getDetail(
      new NextRequest('http://localhost/api/listings/bad'),
      { params: Promise.resolve({ id: 'bad' }) },
    );

    expect(response.status).toBe(400);
    expect(mockedGetDb).not.toHaveBeenCalled();
  });

  it('returns 500 for an unexpected map database failure', async () => {
    mockedGetDb.mockReturnValue({
      collection: () => {
        throw new Error('boom');
      },
    } as never);

    const response = await getMap(new NextRequest('http://localhost/api/listings/map'));

    expect(response.status).toBe(500);
  });
});
