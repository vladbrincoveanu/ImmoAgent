import { describe, it, expect } from '@jest/globals';
import { MapListing } from '@/lib/types';
import { dealScore } from './DealScoreBadge';

// Only the fields dealScore reads matter; the rest of MapListing is irrelevant here.
type ScoreInputs = Partial<
  Pick<MapListing, 'bank_score_confidence' | 'estimated_down_pct' | 'price_vs_avg_pct'>
> & { ubahn_walk_minutes?: number | null };

const listing = (o: ScoreInputs): MapListing => o as unknown as MapListing;

describe('dealScore null gates', () => {
  it('returns null when bank confidence is missing', () => {
    expect(dealScore(listing({ estimated_down_pct: 20 }))).toBeNull();
  });

  it('returns null when the down-payment estimate is missing', () => {
    expect(dealScore(listing({ bank_score_confidence: 'high' }))).toBeNull();
  });

  it('returns null for low confidence with no price-vs-avg signal', () => {
    expect(dealScore(listing({ bank_score_confidence: 'low', estimated_down_pct: 20 }))).toBeNull();
  });

  it('scores low confidence once a price-vs-avg signal exists', () => {
    expect(
      dealScore(listing({ bank_score_confidence: 'low', estimated_down_pct: 20, price_vs_avg_pct: -10 })),
    ).not.toBeNull();
  });
});

describe('dealScore weighting', () => {
  // 0.4 bank + 0.35 price + 0.15 transit + 0.1 confidence = 1.0, so a listing
  // that maxes every sub-score must land on exactly 100.
  it('awards 100 when every sub-score is maximal', () => {
    expect(
      dealScore(
        listing({
          bank_score_confidence: 'high',
          estimated_down_pct: 15, // bankSub = 1.0
          price_vs_avg_pct: -30, // priceSub clamps to 1.0
          ubahn_walk_minutes: 0, // transitSub = 1.0
        }),
      ),
    ).toBe(100);
  });

  // bankSub 0, priceSub 0, transitSub 0, confSub 0.4 → 0.4 * 0.1 = 0.04 → 4
  it('awards only the confidence weight when every other sub-score bottoms out', () => {
    expect(
      dealScore(
        listing({
          bank_score_confidence: 'low',
          estimated_down_pct: 45, // bankSub clamps to 0
          price_vs_avg_pct: 70, // priceSub clamps to 0
          ubahn_walk_minutes: 20, // transitSub = 0
        }),
      ),
    ).toBe(4);
  });

  it('stays within 0..100 for out-of-range inputs', () => {
    const extreme = dealScore(
      listing({
        bank_score_confidence: 'high',
        estimated_down_pct: -500,
        price_vs_avg_pct: -500,
        ubahn_walk_minutes: -500,
      }),
    );
    expect(extreme).toBeGreaterThanOrEqual(0);
    expect(extreme).toBeLessThanOrEqual(100);
  });
});

describe('dealScore defaults for missing optional signals', () => {
  const base: ScoreInputs = { bank_score_confidence: 'high', estimated_down_pct: 15 };

  // Absent price-vs-avg defaults to 0.7, absent transit to 0.5:
  // 1.0*0.4 + 0.7*0.35 + 0.5*0.15 + 1.0*0.1 = 0.82
  it('falls back to neutral sub-scores when price and transit are unknown', () => {
    expect(dealScore(listing(base))).toBe(82);
  });

  it('treats a null walk time as unknown rather than as zero minutes', () => {
    expect(dealScore(listing({ ...base, ubahn_walk_minutes: null }))).toBe(
      dealScore(listing(base)),
    );
  });

  it('ranks a cheaper listing above an identical pricier one', () => {
    const cheap = dealScore(listing({ ...base, price_vs_avg_pct: -20 }))!;
    const pricey = dealScore(listing({ ...base, price_vs_avg_pct: 20 }))!;
    expect(cheap).toBeGreaterThan(pricey);
  });

  it('ranks better-connected listings above worse-connected ones', () => {
    const near = dealScore(listing({ ...base, ubahn_walk_minutes: 2 }))!;
    const far = dealScore(listing({ ...base, ubahn_walk_minutes: 18 }))!;
    expect(near).toBeGreaterThan(far);
  });

  it('ranks confidence high > medium > low', () => {
    const at = (c: 'high' | 'medium' | 'low') =>
      dealScore(listing({ bank_score_confidence: c, estimated_down_pct: 20, price_vs_avg_pct: -5 }))!;
    expect(at('high')).toBeGreaterThan(at('medium'));
    expect(at('medium')).toBeGreaterThan(at('low'));
  });
});
