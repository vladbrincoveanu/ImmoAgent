import { describe, it, expect } from '@jest/globals';
import {
  validateDistrict,
  validateSort,
  validateMinScore,
  validateLimit,
  validateObjectId,
  validateStatus,
} from './validators';

describe('validateDistrict', () => {
  it('returns valid district strings unchanged', () => {
    expect(validateDistrict('1010')).toBe('1010');
    expect(validateDistrict('1230')).toBe('1230');
    expect(validateDistrict('1190')).toBe('1190');
  });

  it('returns null for invalid district codes', () => {
    expect(validateDistrict('9999')).toBeNull();
    expect(validateDistrict('0001')).toBeNull();
    expect(validateDistrict('1049')).toBeNull();
  });

  it('returns null for empty or whitespace input', () => {
    expect(validateDistrict('')).toBeNull();
    expect(validateDistrict('   ')).toBeNull();
    expect(validateDistrict(null)).toBeNull();
  });

  it('trims whitespace from valid districts', () => {
    expect(validateDistrict(' 1010 ')).toBe('1010');
  });

  it('expands single-digit shorthand to the full postal code', () => {
    expect(validateDistrict('1')).toBe('1010');
    expect(validateDistrict('2')).toBe('1020');
    expect(validateDistrict('9')).toBe('1090');
  });

  it('expands zero-padded and two-digit shorthand', () => {
    expect(validateDistrict('01')).toBe('1010');
    expect(validateDistrict('02')).toBe('1020');
    expect(validateDistrict('09')).toBe('1090');
    expect(validateDistrict('10')).toBe('1100');
    expect(validateDistrict('15')).toBe('1150');
    expect(validateDistrict('23')).toBe('1230');
  });

  it('returns null for out-of-range shorthand', () => {
    expect(validateDistrict('0')).toBeNull();
    expect(validateDistrict('24')).toBeNull();
    expect(validateDistrict('99')).toBeNull();
  });
});

describe('validateStatus', () => {
  it('returns valid status options unchanged', () => {
    expect(validateStatus('all')).toBe('all');
    expect(validateStatus('active')).toBe('active');
    expect(validateStatus('taken')).toBe('taken');
  });

  it('returns all for invalid or null input', () => {
    expect(validateStatus('archived')).toBe('all');
    expect(validateStatus('')).toBe('all');
    expect(validateStatus(null)).toBe('all');
  });
});

describe('validateSort', () => {
  it('returns valid sort options unchanged', () => {
    expect(validateSort('score_desc')).toBe('score_desc');
    expect(validateSort('price_asc')).toBe('price_asc');
    expect(validateSort('price_desc')).toBe('price_desc');
    expect(validateSort('date_desc')).toBe('date_desc');
    expect(validateSort('area_desc')).toBe('area_desc');
  });

  it('returns score_desc for invalid or null input', () => {
    expect(validateSort('invalid')).toBe('score_desc');
    expect(validateSort('')).toBe('score_desc');
    expect(validateSort(null)).toBe('score_desc');
  });
});

describe('validateMinScore', () => {
  it('returns parsed floats within range', () => {
    expect(validateMinScore('50')).toBe(50);
    expect(validateMinScore('0')).toBe(0);
    expect(validateMinScore('100')).toBe(100);
    expect(validateMinScore('75.5')).toBe(75.5);
  });

  it('clamps values above 100 to 100', () => {
    expect(validateMinScore('150')).toBe(100);
    expect(validateMinScore('999')).toBe(100);
  });

  it('clamps values below 0 to 0', () => {
    expect(validateMinScore('-10')).toBe(0);
  });

  it('returns 0 for non-numeric input', () => {
    expect(validateMinScore('abc')).toBe(0);
    expect(validateMinScore('')).toBe(0);
    expect(validateMinScore(null)).toBe(0);
  });
});

describe('validateLimit', () => {
  it('returns parsed ints within range', () => {
    expect(validateLimit('50', 200)).toBe(50);
    expect(validateLimit('1', 200)).toBe(1);
    expect(validateLimit('200', 200)).toBe(200);
  });

  it('clamps values above max to max', () => {
    expect(validateLimit('500', 200)).toBe(200);
  });

  it('clamps values below 1 to 1', () => {
    expect(validateLimit('0', 200)).toBe(1);
    expect(validateLimit('-5', 200)).toBe(1);
  });

  it('returns max for non-numeric input', () => {
    expect(validateLimit('abc', 200)).toBe(200);
    expect(validateLimit('', 200)).toBe(200);
    expect(validateLimit(null, 200)).toBe(200);
  });
});

describe('validateObjectId', () => {
  it('returns valid 24-char hex strings unchanged', () => {
    expect(validateObjectId('507f1f77bcf86cd799439011')).toBe('507f1f77bcf86cd799439011');
  });

  it('returns null for invalid IDs', () => {
    expect(validateObjectId('too-short')).toBeNull();
    expect(validateObjectId('not-a-valid-objectid!!!')).toBeNull();
    expect(validateObjectId('')).toBeNull();
    expect(validateObjectId(null)).toBeNull();
  });

  it('rejects hex strings with non-hex characters', () => {
    expect(validateObjectId('507f1f77bcf86cd79943901z')).toBeNull();
  });
});

describe('strict numeric parsing', () => {
  it('rejects partial numeric prefixes', () => {
    expect(validateMinScore('10abc')).toBe(0);
    expect(validateLimit('3items', 200)).toBe(200);
  });

  it('rejects non-finite values', () => {
    expect(validateMinScore('NaN')).toBe(0);
    expect(validateMinScore('Infinity')).toBe(0);
    expect(validateLimit('NaN', 200)).toBe(200);
    expect(validateLimit('Infinity', 200)).toBe(200);
  });
});
