import { describe, expect, it } from '@jest/globals';
import { estimateWalkMinutes, haversineKm } from './geo';

describe('geo helpers', () => {
  it('returns zero for identical coordinates', () => {
    expect(haversineKm({ lat: 48.2, lon: 16.37 }, { lat: 48.2, lon: 16.37 })).toBe(0);
  });

  it('is symmetric and produces a positive Vienna-scale distance', () => {
    const a = { lat: 48.2082, lon: 16.3738 };
    const b = { lat: 48.198, lon: 16.369 };

    expect(haversineKm(a, b)).toBeGreaterThan(1);
    expect(haversineKm(a, b)).toBeCloseTo(haversineKm(b, a), 8);
  });

  it('uses the walking speed used by the current commute filter', () => {
    expect(estimateWalkMinutes(4.8)).toBe(60);
  });
});
