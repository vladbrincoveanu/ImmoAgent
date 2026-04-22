export const SOURCE_LABELS: Record<string, string> = {
  willhaben: 'WH',
  immo_kurier: 'IK',
  derstandard: 'DS',
  unknown: '?',
};

export function formatPrice(priceTotal: number | null, isEstimated?: boolean): string {
  if (priceTotal == null) return 'Price on request';
  return `${isEstimated ? '~' : ''}€${priceTotal.toLocaleString('de-AT')}`;
}
