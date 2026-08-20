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
});
