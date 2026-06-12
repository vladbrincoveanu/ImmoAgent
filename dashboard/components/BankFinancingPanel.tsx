'use client';

import React, { useState } from 'react';

// Austrian bank LTV bands and interest rates (2026 indicative).
// Source: BAWAG/Erste/Raiffeisen public rate sheets (illustrative).
interface BankTier {
  ltvMax: number; // max LTV ratio
  fixedRate: number; // 20yr fixed, indicative
  variableMargin: number; // Euribor + margin
  processingFeePct: number; // % of loan
}

interface Bank {
  name: string;
  color: string;
  tiers: BankTier[];
}

const BANKS: Bank[] = [
  {
    name: 'BAWAG',
    color: 'bg-red-50 border-red-200 text-red-800',
    tiers: [
      { ltvMax: 0.6, fixedRate: 2.9, variableMargin: 0.6, processingFeePct: 0.5 },
      { ltvMax: 0.8, fixedRate: 3.3, variableMargin: 0.9, processingFeePct: 0.5 },
      { ltvMax: 0.9, fixedRate: 3.6, variableMargin: 1.2, processingFeePct: 0.5 },
      { ltvMax: 1.0, fixedRate: 4.1, variableMargin: 1.7, processingFeePct: 0.5 },
    ],
  },
  {
    name: 'Erste Bank',
    color: 'bg-amber-50 border-amber-200 text-amber-800',
    tiers: [
      { ltvMax: 0.6, fixedRate: 2.8, variableMargin: 0.55, processingFeePct: 0.5 },
      { ltvMax: 0.8, fixedRate: 3.2, variableMargin: 0.85, processingFeePct: 0.5 },
      { ltvMax: 0.9, fixedRate: 3.5, variableMargin: 1.15, processingFeePct: 0.5 },
      { ltvMax: 1.0, fixedRate: 4.0, variableMargin: 1.65, processingFeePct: 0.5 },
    ],
  },
  {
    name: 'Raiffeisen',
    color: 'bg-blue-50 border-blue-200 text-blue-800',
    tiers: [
      { ltvMax: 0.6, fixedRate: 2.95, variableMargin: 0.65, processingFeePct: 0.5 },
      { ltvMax: 0.8, fixedRate: 3.35, variableMargin: 0.9, processingFeePct: 0.5 },
      { ltvMax: 0.9, fixedRate: 3.65, variableMargin: 1.2, processingFeePct: 0.5 },
      { ltvMax: 1.0, fixedRate: 4.15, variableMargin: 1.7, processingFeePct: 0.5 },
    ],
  },
];

function calcMonthly(loan: number, ratePct: number, years: number): number {
  if (loan <= 0 || ratePct <= 0) return 0;
  const r = ratePct / 100 / 12;
  const n = years * 12;
  return (loan * r * Math.pow(1 + r, n)) / (Math.pow(1 + r, n) - 1);
}

interface BankFinancingPanelProps {
  priceTotal: number | null;
  downPaymentPct?: number;
  years?: number;
}

export function BankFinancingPanel({ priceTotal, downPaymentPct = 20, years = 25 }: BankFinancingPanelProps) {
  const [showFull, setShowFull] = useState(false);

  if (!priceTotal || priceTotal <= 0) return null;
  const ltv = (100 - downPaymentPct) / 100;
  const loan = priceTotal * ltv;
  const equity = priceTotal - loan;

  const rows = BANKS.map((b) => {
    const tier = b.tiers.find((t) => ltv <= t.ltvMax) || b.tiers[b.tiers.length - 1];
    const rate = tier.fixedRate;
    const monthly = Math.round(calcMonthly(loan, rate, years));
    const fee = Math.round(loan * (tier.processingFeePct / 100));
    return { bank: b, tier, rate, monthly, fee };
  });

  const cheapest = rows.reduce((a, b) => (a.monthly <= b.monthly ? a : b));
  const best = rows.findIndex((r) => r.bank.name === cheapest.bank.name);

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4" data-testid="bank-financing-panel">
      <div className="flex items-center justify-between mb-2">
        <h4 className="text-sm font-semibold text-gray-800">
          Austrian bank financing · {downPaymentPct}% down
        </h4>
        <button
          type="button"
          onClick={() => setShowFull(!showFull)}
          className="text-xs text-blue-600 hover:underline"
        >
          {showFull ? 'Hide' : 'Compare all 3'}
        </button>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs">
        {rows.map((r, i) => (
          <div
            key={r.bank.name}
            className={`rounded-md border p-2 ${r.bank.color} ${i === best ? 'ring-2 ring-green-400' : ''}`}
            data-testid={`bank-rate-${r.bank.name.toLowerCase().replace(/\s+/g, '-')}`}
          >
            <p className="font-semibold text-sm">
              {r.bank.name} {i === best && <span className="text-[10px]">✓ best</span>}
            </p>
            <p className="text-[11px] opacity-80">≤{Math.round(r.tier.ltvMax * 100)}% LTV</p>
            <p className="text-base font-bold mt-1">
              {r.monthly.toLocaleString('de-AT')} €/mo
            </p>
            {showFull && (
              <>
                <p className="text-[11px]">Rate: {r.rate.toFixed(2)}% · {years}yr fix</p>
                <p className="text-[11px]">Fee: {r.fee.toLocaleString('de-AT')} €</p>
              </>
            )}
          </div>
        ))}
      </div>
      <p className="text-[10px] text-muted mt-2">
        Loan: {Math.round(loan).toLocaleString('de-AT')} € · Equity: {Math.round(equity).toLocaleString('de-AT')} €. Indicative rates as of 2026.
      </p>
    </div>
  );
}
