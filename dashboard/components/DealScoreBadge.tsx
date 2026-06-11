'use client';

import React from 'react';
import { MapListing } from '@/lib/types';

interface DealScoreBadgeProps {
  listing: MapListing;
}

const BANK_FACTOR_WEIGHT = 0.4;
const PRICE_VS_AVG_WEIGHT = 0.35;
const TRANSIT_WEIGHT = 0.15;
const CONFIDENCE_WEIGHT = 0.1;

export function dealScore(listing: MapListing): number | null {
  if (listing.bank_score_confidence == null || listing.estimated_down_pct == null) return null;
  if (listing.bank_score_confidence === 'low' && listing.price_vs_avg_pct == null) return null;

  // Bank sub-score: lower down_pct = better (full equity at 20% down → 1.0, 30% down → 0.6)
  const bankSub = Math.max(0, Math.min(1, 1 - (listing.estimated_down_pct - 15) / 30));

  // Price-vs-avg sub-score: -20% → 1.0, 0% → 0.7, +20% → 0.3
  let priceSub = 0.7;
  if (listing.price_vs_avg_pct != null) {
    priceSub = Math.max(0, Math.min(1, 0.7 - listing.price_vs_avg_pct / 100));
  }

  // Transit sub-score: ubahn_walk_minutes lower = better. None → 0.5
  const transitRaw = (listing as { ubahn_walk_minutes?: number | null }).ubahn_walk_minutes;
  let transitSub = 0.5;
  if (typeof transitRaw === 'number') {
    transitSub = Math.max(0, Math.min(1, 1 - transitRaw / 20));
  }

  // Confidence sub-score
  const confSub = listing.bank_score_confidence === 'high' ? 1.0 : listing.bank_score_confidence === 'medium' ? 0.7 : 0.4;

  const score = bankSub * BANK_FACTOR_WEIGHT + priceSub * PRICE_VS_AVG_WEIGHT + transitSub * TRANSIT_WEIGHT + confSub * CONFIDENCE_WEIGHT;
  return Math.round(score * 100);
}

export function DealScoreBadge({ listing }: DealScoreBadgeProps) {
  const score = dealScore(listing);
  if (score == null) return null;
  let cls = 'bg-red-100 text-red-800';
  let label = 'Risky';
  if (score >= 70) { cls = 'bg-green-100 text-green-800'; label = 'Great deal'; }
  else if (score >= 55) { cls = 'bg-emerald-100 text-emerald-800'; label = 'Good deal'; }
  else if (score >= 40) { cls = 'bg-yellow-100 text-yellow-800'; label = 'Fair'; }
  return (
    <span
      className={`text-[9px] font-bold rounded px-1.5 py-0.5 ${cls}`}
      title={`Deal Score ${score}/100 — bank financing (40%) + price vs zone avg (35%) + transit (15%) + bank confidence (10%)`}
    >
      {score} · {label}
    </span>
  );
}
