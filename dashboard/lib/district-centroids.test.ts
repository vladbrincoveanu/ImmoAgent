import { describe, it, expect } from '@jest/globals';
import { DISTRICT_CENTROIDS, getDistrictCentroid, resolveCoordinates } from './district-centroids';

describe('getDistrictCentroid', () => {
  it('returns the centroid for every known Vienna district', () => {
    for (const bezirk of Object.keys(DISTRICT_CENTROIDS)) {
      expect(getDistrictCentroid(bezirk)).toEqual(DISTRICT_CENTROIDS[bezirk]);
    }
  });

  it('covers all 23 districts', () => {
    expect(Object.keys(DISTRICT_CENTROIDS)).toHaveLength(23);
  });

  it('returns null for unknown or empty input', () => {
    expect(getDistrictCentroid('9999')).toBeNull();
    expect(getDistrictCentroid('02')).toBeNull(); // shorthand must be normalised first
    expect(getDistrictCentroid('')).toBeNull();
    expect(getDistrictCentroid(null)).toBeNull();
    expect(getDistrictCentroid(undefined)).toBeNull();
  });

  it('places every centroid inside Vienna\'s bounding box', () => {
    for (const [bezirk, { lat, lon }] of Object.entries(DISTRICT_CENTROIDS)) {
      expect(lat).toBeGreaterThan(48.1);
      expect(lat).toBeLessThan(48.35);
      expect(lon).toBeGreaterThan(16.15);
      expect(lon).toBeLessThan(16.6);
      expect(bezirk).toMatch(/^1\d{2}0$/);
    }
  });
});

describe('resolveCoordinates', () => {
  it('prefers stored coordinates over the district centroid', () => {
    const stored = { lat: 48.2, lon: 16.37 };
    expect(resolveCoordinates(stored, '1230')).toBe(stored);
  });

  it('falls back to the district centroid when coordinates are missing', () => {
    expect(resolveCoordinates(null, '1010')).toEqual(DISTRICT_CENTROIDS['1010']);
    expect(resolveCoordinates(undefined, '1010')).toEqual(DISTRICT_CENTROIDS['1010']);
  });

  it('falls back when stored coordinates are structurally invalid', () => {
    const bad = { lat: '48.2', lon: 16.37 } as unknown as { lat: number; lon: number };
    expect(resolveCoordinates(bad, '1020')).toEqual(DISTRICT_CENTROIDS['1020']);
  });

  it('returns null when neither coordinates nor a known district are available', () => {
    expect(resolveCoordinates(null, null)).toBeNull();
    expect(resolveCoordinates(null, '9999')).toBeNull();
    expect(resolveCoordinates(undefined, undefined)).toBeNull();
  });
});
