// Inline copy of validators.ts (just the bits the route uses).
// Kept in sync with the real file at lib/validators.ts.
const VALID_DISTRICTS = new Set([
  '1010', '1020', '1030', '1040', '1050', '1060', '1070', '1080', '1090',
  '1100', '1110', '1120', '1130', '1140', '1150', '1160', '1170', '1180',
  '1190', '1200', '1210', '1220', '1230',
]);

const SHORT_TO_LONG = {
  '1': '1010', '2': '1020', '3': '1030', '4': '1040', '5': '1050',
  '6': '1060', '7': '1070', '8': '1080', '9': '1090',
  '01': '1010', '02': '1020', '03': '1030', '04': '1040', '05': '1050',
  '06': '1060', '07': '1070', '08': '1080', '09': '1090',
  '10': '1100', '11': '1110', '12': '1120', '13': '1130', '14': '1140',
  '15': '1150', '16': '1160', '17': '1170', '18': '1180', '19': '1190',
  '20': '1200', '21': '1210', '22': '1220', '23': '1230',
};

export function validateDistrict(input) {
  if (!input || String(input).trim() === '') return null;
  const trimmed = String(input).trim();
  if (VALID_DISTRICTS.has(trimmed)) return trimmed;
  return SHORT_TO_LONG[trimmed] ?? null;
}
