import { beforeEach, describe, expect, it, jest } from '@jest/globals';
import { NextRequest } from 'next/server';
import { getDb } from '@/lib/mongodb';
import { GET as getMap } from './listings/map/route';
import { GET as getDetail } from './listings/[id]/route';
import { GET as getInsights } from './insights/route';

jest.mock('@/lib/mongodb', () => ({
  getDb: jest.fn(),
  ObjectId: class ObjectId {
    constructor(readonly value: string) {}

    toString() {
      return this.value;
    }
  },
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
    expect(await response.json()).toEqual({ error: 'Database unavailable' });
  });

  it('returns 400 before database access for an invalid detail id', async () => {
    const response = await getDetail(
      new NextRequest('http://localhost/api/listings/bad'),
      { params: Promise.resolve({ id: 'bad' }) },
    );

    expect(response.status).toBe(400);
    expect(await response.json()).toEqual({ error: 'Invalid listing ID', field: 'id' });
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
    expect(await response.json()).toEqual({ error: 'Database error' });
  });

  it('computes insight secondary counts in Mongo without materializing listings', async () => {
    const cursor = (value: unknown[]) => ({
      toArray: () => Promise.resolve(value),
    });
    const aggregate = (jest.fn() as jest.Mock)
      .mockReturnValueOnce(cursor([{
          _id: null,
          count: 1,
          avg_price: 420000,
          avg_price_per_m2: 7000,
          avg_score: 72,
          unfinanceable_count: 0,
          district_count: 1,
        }]))
      .mockReturnValueOnce(cursor([{
          below_avg_count: 1,
          good_transit_count: 1,
        }]));
    const find = jest.fn();
    const db = {
      collection: jest.fn(() => ({ aggregate, find })),
    };
    mockedGetDb.mockReturnValue(db as never);

    const response = await getInsights(new NextRequest('http://localhost/api/insights'));

    expect(response.status).toBe(200);
    expect(find).not.toHaveBeenCalled();
    expect(aggregate).toHaveBeenCalledTimes(2);
    expect(aggregate.mock.calls[1][0]).toContainEqual(expect.objectContaining({
      $setWindowFields: expect.any(Object),
    }));
  });
});
