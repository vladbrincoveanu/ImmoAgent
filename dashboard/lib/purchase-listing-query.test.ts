import { purchasePricePerSqmConditions } from './purchase-listing-query';

describe('purchase listing price validation', () => {
  it('uses shared GLOBAL_VALIDATION thresholds', () => {
    expect(purchasePricePerSqmConditions()).toEqual([
      { is_genossenschaft: { $ne: true } },
      { $expr: { $gte: [{ $divide: ['$price_total', '$area_m2'] }, 1000] } },
      { $expr: { $lte: [{ $divide: ['$price_total', '$area_m2'] }, 20000] } },
    ]);
  });
});
