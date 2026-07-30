import { describe, it, expect } from '@jest/globals';
import { PROFILES, PROFILE_KEYS, DEFAULT_PROFILE, isValidProfile } from './profile';

describe('PROFILES', () => {
  it('exposes a unique, non-empty key for every profile', () => {
    expect(PROFILES.length).toBeGreaterThan(0);
    for (const p of PROFILES) {
      expect(p.key).toMatch(/^[a-z][a-z_]*$/);
      expect(p.label.length).toBeGreaterThan(0);
      expect(p.description.length).toBeGreaterThan(0);
    }
    expect(new Set(PROFILE_KEYS).size).toBe(PROFILE_KEYS.length);
  });

  it('includes the default profile', () => {
    expect(PROFILE_KEYS).toContain(DEFAULT_PROFILE);
  });
});

describe('isValidProfile', () => {
  it('accepts every declared profile key', () => {
    for (const key of PROFILE_KEYS) {
      expect(isValidProfile(key)).toBe(true);
    }
  });

  it('rejects unknown, empty, and non-string input', () => {
    expect(isValidProfile('not_a_profile')).toBe(false);
    expect(isValidProfile('')).toBe(false);
    expect(isValidProfile(null)).toBe(false);
    expect(isValidProfile(undefined)).toBe(false);
  });

  it('is case-sensitive', () => {
    expect(isValidProfile('DEFAULT')).toBe(false);
    expect(isValidProfile('Owner_Occupier')).toBe(false);
  });

  it('rejects inherited Object.prototype keys', () => {
    // PROFILE_KEYS.includes() must not be fooled by prototype members.
    expect(isValidProfile('constructor')).toBe(false);
    expect(isValidProfile('toString')).toBe(false);
  });
});
