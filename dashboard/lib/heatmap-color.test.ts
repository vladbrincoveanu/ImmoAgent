import { describe, it, expect } from '@jest/globals';
import { HEATMAP_MIN, HEATMAP_MAX, priceToColor } from './heatmap-color';

const rgb = (s: string): [number, number, number] => {
  const m = s.match(/^rgb\((\d+), (\d+), (\d+)\)$/);
  if (!m) throw new Error(`not an rgb() string: ${s}`);
  return [Number(m[1]), Number(m[2]), Number(m[3])];
};

describe('heatmap bounds', () => {
  // These mirror scoring.py NORMALIZATION_RANGES.price_per_m2. If the Python
  // side moves, this test must move with it — the legend would otherwise lie.
  it('pins the price-per-m² range shared with scoring.py', () => {
    expect(HEATMAP_MIN).toBe(3500);
    expect(HEATMAP_MAX).toBe(8000);
  });
});

describe('priceToColor', () => {
  it('renders the cheapest end green and the priciest end red', () => {
    const [r0, g0, b0] = rgb(priceToColor(HEATMAP_MIN));
    expect(g0).toBeGreaterThan(r0);
    expect(g0).toBeGreaterThan(b0);

    const [r1, g1, b1] = rgb(priceToColor(HEATMAP_MAX));
    expect(r1).toBeGreaterThan(g1);
    expect(r1).toBeGreaterThan(b1);
  });

  it('renders the midpoint yellow', () => {
    expect(priceToColor((HEATMAP_MIN + HEATMAP_MAX) / 2)).toBe('rgb(255, 221, 100)');
  });

  it('clamps prices outside the range to the endpoint colors', () => {
    expect(priceToColor(0)).toBe(priceToColor(HEATMAP_MIN));
    expect(priceToColor(-1000)).toBe(priceToColor(HEATMAP_MIN));
    expect(priceToColor(999_999)).toBe(priceToColor(HEATMAP_MAX));
  });

  it('always returns a parseable rgb() string with channels in 0..255', () => {
    for (let p = 0; p <= 12_000; p += 250) {
      for (const c of rgb(priceToColor(p))) {
        expect(c).toBeGreaterThanOrEqual(0);
        expect(c).toBeLessThanOrEqual(255);
      }
    }
  });

  // The raw red channel is NOT monotonic — it climbs 26→255 to reach yellow,
  // then falls back to 215 at red. Warmth (red relative to green) is the
  // property that actually holds end to end: pricier always looks hotter.
  it('grows monotonically warmer as price rises', () => {
    let prevWarmth = -Infinity;
    for (let p = HEATMAP_MIN; p <= HEATMAP_MAX; p += 100) {
      const [r, g] = rgb(priceToColor(p));
      const warmth = r / g;
      expect(warmth).toBeGreaterThan(prevWarmth);
      prevWarmth = warmth;
    }
  });
});
