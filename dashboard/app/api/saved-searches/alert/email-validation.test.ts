import { isValidAlertEmail } from './email-validation';

describe('isValidAlertEmail', () => {
  it('accepts a normal address', () => {
    expect(isValidAlertEmail('alerts@example.com')).toBe(true);
  });

  it('rejects malformed addresses without regex backtracking', () => {
    expect(isValidAlertEmail('!@!.'.repeat(10000))).toBe(false);
    expect(isValidAlertEmail('missing-domain@')).toBe(false);
    expect(isValidAlertEmail('has spaces@example.com')).toBe(false);
  });
});
