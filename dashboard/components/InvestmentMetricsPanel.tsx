'use client';

import React, { useMemo } from 'react';

interface InvestmentMetricsPanelProps {
  priceTotal: number | null | undefined;
  areaM2: number | null | undefined;
  bezirk: string | null | undefined;
  downPaymentPct?: number;
  monthlyRentOverride?: number;
}

const RENT_PER_M2: Record<string, number> = {
  '1010': 26, '1020': 20, '1030': 19, '1040': 19, '1050': 18, '1060': 18, '1070': 19,
  '1080': 19, '1090': 20, '1100': 16, '1110': 14, '1120': 15, '1130': 17, '1140': 15,
  '1150': 15, '1160': 15, '1170': 16, '1180': 17, '1190': 17, '1200': 16, '1210': 13,
  '1220': 13, '1230': 12,
};
const DEFAULT_RPM2 = 15;
const VACANCY_RATE = 0.08; // 8% Vienna avg
const MAINT_PCT_OF_REVENUE = 0.15;
const MGMT_PCT_OF_REVENUE = 0.07;
const INSURANCE_TAX_PCT_OF_REVENUE = 0.04;
const INTEREST_RATE = 3.4; // weighted avg, indicative
const APPRECIATION_PCT = 0.025; // Vienna long-term avg

export function InvestmentMetricsPanel({
  priceTotal,
  areaM2,
  bezirk,
  downPaymentPct = 20,
  monthlyRentOverride,
}: InvestmentMetricsPanelProps) {
  const metrics = useMemo(() => {
    if (!priceTotal || !areaM2) return null;
    const rpm2 = monthlyRentOverride && monthlyRentOverride > 0
      ? monthlyRentOverride / areaM2
      : (bezirk && RENT_PER_M2[bezirk]) || DEFAULT_RPM2;
    const monthlyRent = monthlyRentOverride && monthlyRentOverride > 0
      ? monthlyRentOverride
      : Math.round(areaM2 * rpm2);
    const annualRent = monthlyRent * 12;
    const vacancy = annualRent * VACANCY_RATE;
    const effectiveRent = annualRent - vacancy;
    const maintenance = effectiveRent * MAINT_PCT_OF_REVENUE;
    const management = effectiveRent * MGMT_PCT_OF_REVENUE;
    const insuranceTax = effectiveRent * INSURANCE_TAX_PCT_OF_REVENUE;
    const noi = effectiveRent - maintenance - management - insuranceTax;

    const downPayment = priceTotal * (downPaymentPct / 100);
    const loan = priceTotal - downPayment;
    const annualDebtService = loan > 0 ? calcAnnualDebtService(loan, INTEREST_RATE, 25) : 0;
    const cashFlow = noi - annualDebtService;
    const capRate = (noi / priceTotal) * 100;
    const cashOnCash = downPayment > 0 ? (cashFlow / downPayment) * 100 : null;
    const grossYield = (annualRent / priceTotal) * 100;
    const paybackYears = noi > 0 ? priceTotal / noi : Infinity;
    const leverageReturn = (noi / downPayment) * 100;

    // Sensitivity table: -20% rent → -10% → baseline → +10% → +20%
    const sensitivities = [-20, -10, 0, 10, 20].map((pct) => {
      const adjRent = (annualRent * (1 + pct / 100)) * (1 - VACANCY_RATE);
      const adjNoi = adjRent - (adjRent * (MAINT_PCT_OF_REVENUE + MGMT_PCT_OF_REVENUE + INSURANCE_TAX_PCT_OF_REVENUE));
      const adjCash = adjNoi - annualDebtService;
      return { rentPct: pct, cashFlow: Math.round(adjCash), cashOnCash: downPayment > 0 ? ((adjCash / downPayment) * 100).toFixed(1) : null };
    });

    return {
      monthlyRent,
      annualRent,
      effectiveRent: Math.round(effectiveRent),
      noi: Math.round(noi),
      annualDebtService: Math.round(annualDebtService),
      cashFlow: Math.round(cashFlow),
      capRate: capRate.toFixed(1),
      cashOnCash: cashOnCash?.toFixed(1) ?? '0',
      grossYield: grossYield.toFixed(1),
      paybackYears: paybackYears === Infinity ? '∞' : paybackYears.toFixed(1),
      leverageReturn: leverageReturn.toFixed(1),
      downPayment: Math.round(downPayment),
      sensitivities,
      isPositiveCashFlow: cashFlow > 0,
    };
  }, [priceTotal, areaM2, bezirk, downPaymentPct, monthlyRentOverride]);

  if (!metrics) return null;
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4" data-testid="investment-metrics-panel">
      <h4 className="text-sm font-semibold text-gray-800 mb-2">
        Investment metrics · {metrics.downPayment.toLocaleString('de-AT')} € down
      </h4>
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 text-xs">
        <Metric label="Monthly rent" value={`${metrics.monthlyRent.toLocaleString('de-AT')} €`} tone="neutral" />
        <Metric label="Cap rate" value={`${metrics.capRate}%`} tone={Number(metrics.capRate) >= 4 ? 'good' : 'warn'} />
        <Metric label="Cash flow / yr" value={`${metrics.cashFlow.toLocaleString('de-AT')} €`} tone={metrics.isPositiveCashFlow ? 'good' : 'warn'} />
        <Metric label="Cash-on-cash" value={`${metrics.cashOnCash}%`} tone={Number(metrics.cashOnCash) >= 5 ? 'good' : 'warn'} />
        <Metric label="NOI / yr" value={`${metrics.noi.toLocaleString('de-AT')} €`} tone="neutral" />
        <Metric label="Payback" value={`${metrics.paybackYears} yr`} tone="neutral" />
        <Metric label="Gross yield" value={`${metrics.grossYield}%`} tone="neutral" />
        <Metric label="Leveraged ROI" value={`${metrics.leverageReturn}%`} tone="good" />
      </div>
      <div className="mt-3 pt-3 border-t border-gray-100">
        <p className="text-[10px] uppercase tracking-wide text-muted font-semibold mb-1">Sensitivity to rent changes</p>
        <div className="grid grid-cols-5 gap-1 text-[10px]">
          {metrics.sensitivities.map((s) => (
            <div
              key={s.rentPct}
              className={`text-center rounded p-1 ${
                Number(s.cashOnCash) > 0 ? 'bg-green-50' : 'bg-red-50'
              }`}
              data-testid={`sensitivity-${s.rentPct}`}
            >
              <div className="font-semibold">{s.rentPct > 0 ? '+' : ''}{s.rentPct}%</div>
              <div className="text-[9px] text-muted">{s.cashOnCash ?? '0'}%</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone: 'good' | 'warn' | 'neutral' }) {
  const cls = tone === 'good' ? 'text-green-700' : tone === 'warn' ? 'text-red-700' : 'text-gray-800';
  return (
    <div>
      <p className="text-[10px] uppercase text-muted tracking-wide font-semibold">{label}</p>
      <p className={`text-sm font-semibold ${cls}`}>{value}</p>
    </div>
  );
}

function calcAnnualDebtService(loan: number, ratePct: number, years: number): number {
  if (loan <= 0) return 0;
  const r = ratePct / 100 / 12;
  const n = years * 12;
  const monthly = (loan * r * Math.pow(1 + r, n)) / (Math.pow(1 + r, n) - 1);
  return monthly * 12;
}
