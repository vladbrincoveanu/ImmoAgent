// Keep purchase-listing gates aligned with Project/Application/buyer_profiles.py.
export function purchasePricePerSqmConditions() {
  return [
    { is_genossenschaft: { $ne: true } },
    { $expr: { $gte: [{ $divide: ['$price_total', '$area_m2'] }, 1000] } },
    { $expr: { $lte: [{ $divide: ['$price_total', '$area_m2'] }, 20000] } },
  ];
}
