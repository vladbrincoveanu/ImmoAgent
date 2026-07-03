// dashboard/lib/heatmap-color.ts
// Price-per-m² → color, aligned to scoring.py NORMALIZATION_RANGES.price_per_m2
// (min_val 3500 = best/cheapest = green, max_val 8000 = worst/priciest = red).
export const HEATMAP_MIN = 3500;
export const HEATMAP_MAX = 8000;

type RGB = [number, number, number];
const GREEN: RGB = [26, 152, 80];
const YELLOW: RGB = [255, 221, 100];
const RED: RGB = [215, 48, 39];

const lerp = (a: number, b: number, t: number) => Math.round(a + (b - a) * t);
const mix = (c1: RGB, c2: RGB, t: number) =>
  `rgb(${lerp(c1[0], c2[0], t)}, ${lerp(c1[1], c2[1], t)}, ${lerp(c1[2], c2[2], t)})`;

export function priceToColor(pricePerM2: number): string {
  const t = Math.max(0, Math.min(1, (pricePerM2 - HEATMAP_MIN) / (HEATMAP_MAX - HEATMAP_MIN)));
  return t <= 0.5 ? mix(GREEN, YELLOW, t / 0.5) : mix(YELLOW, RED, (t - 0.5) / 0.5);
}
