'use client';

import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import { ListingDetail as ListingDetailType } from '@/lib/types';
import { ScoreBadge } from './ScoreBadge';
import { CommuteAndRentPanel } from './CommuteAndRentPanel';
import { AddressBlock } from './AddressBlock';
import { BankFinancingPanel } from './BankFinancingPanel';
import { InvestmentMetricsPanel } from './InvestmentMetricsPanel';
import { DistrictTrendChart } from './DistrictTrendChart';
import { TimeOnMarketBadge, PriceDropBadge } from './MarketBadges';

interface ListingDetailProps {
  id: string;
  onClose: () => void;
}

type TabKey = 'overview' | 'financing' | 'investment' | 'area';

interface ZoneStats {
  district: string;
  total_in_district: number;
  avg_price: number | null;
  avg_price_per_m2: number | null;
  min_price: number | null;
  max_price: number | null;
  avg_area: number | null;
  avg_rooms: number | null;
  this_listing: {
    price: number | null;
    price_per_m2: number | null;
    price_vs_avg_pct: number | null;
    price_per_m2_vs_avg_pct: number | null;
  };
  matching_budget: number;
  avg_ubahn_minutes: number | null;
  avg_school_minutes: number | null;
}

export function ListingDetail({ id, onClose }: ListingDetailProps) {
  const searchParams = useSearchParams();
  const destLat = searchParams.get('dest_lat');
  const destLon = searchParams.get('dest_lon');
  const destName = searchParams.get('dest_name') ?? '';
  const [listing, setListing] = useState<ListingDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);
  const [urlValid, setUrlValid] = useState<boolean | null>(null);
  const [imageError, setImageError] = useState(false);
  const [tab, setTab] = useState<TabKey>('overview');
  const [zoneStats, setZoneStats] = useState<ZoneStats | null>(null);
  const [comparables, setComparables] = useState<Array<{
    _id: string;
    title: string | null;
    url: string;
    price_total: number | null;
    area_m2: number | null;
    rooms: number | null;
    bezirk: string | null;
    score: number | null;
    image_url: string | null;
    source_enum: string | null;
    price_per_m2: number;
    better_deal: boolean;
  }> | null>(null);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  useEffect(() => {
    setImageError(false);
    setUrlValid(null);
    setZoneStats(null);
    setComparables(null);
    setTab('overview');
    fetch(`/api/listings/${id}`)
      .then((r) => r.json())
      .then((data) => {
        setListing(data);
        setUrlValid(data.url_is_valid ?? null);
      })
      .finally(() => setLoading(false));
    fetch(`/api/listings/${id}/zone-stats`)
      .then((r) => r.json())
      .then(setZoneStats)
      .catch(() => {});
    fetch(`/api/listings/${id}/comparables`)
      .then((r) => r.json())
      .then((d) => setComparables(d.comparables ?? []))
      .catch(() => setComparables([]));
  }, [id]);

  const handleRecheck = async () => {
    setChecking(true);
    try {
      const res = await fetch(`/api/listings/${id}/check`, { method: 'POST' });
      const data = await res.json();
      setUrlValid(data.url_is_valid);
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[2000] flex items-center justify-center bg-black/50 p-4" onClick={onClose}>
      <div className="bg-white rounded-2xl shadow-xl max-w-2xl w-full max-h-[90vh] flex flex-col overflow-hidden" onClick={(e) => e.stopPropagation()}>
        {loading ? (
          <div className="p-8 text-center text-gray-500 relative">
            <button
              onClick={onClose}
              className="absolute top-3 right-4 text-gray-400 hover:text-gray-600 text-2xl leading-none"
            >
              &times;
            </button>
            Loading...
          </div>
        ) : listing ? (
          (() => {
            const hasFinancing = listing.price_total != null;
            const hasInvestment = listing.price_total != null && listing.area_m2 != null;
            const hasArea = listing.bezirk != null;
            const tabs: { key: TabKey; label: string; show: boolean }[] = [
              { key: 'overview', label: 'Overview', show: true },
              { key: 'financing', label: 'Financing', show: hasFinancing },
              { key: 'investment', label: 'Investment', show: hasInvestment },
              { key: 'area', label: 'Area & Market', show: hasArea },
            ];
            const active = tabs.find((t) => t.key === tab && t.show) ? tab : 'overview';

            return (
              <>
                {/* Sticky summary header — persists across every tab */}
                <div className="shrink-0 border-b border-gray-200 px-6 pt-4 pb-3">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <ScoreBadge score={listing.score} />
                        <TimeOnMarketBadge processedAt={listing.processed_at} />
                        <PriceDropBadge priceHistory={listing.price_history} currentPrice={listing.price_total} />
                      </div>
                      <h2 className="mt-1.5 text-lg font-bold text-gray-900 truncate" title={listing.title || listing.address || ''}>
                        {listing.title || listing.address || 'Untitled Property'}
                      </h2>
                    </div>
                    <button
                      onClick={onClose}
                      className="shrink-0 text-gray-400 hover:text-gray-600 text-2xl leading-none"
                      aria-label="Close"
                    >
                      &times;
                    </button>
                  </div>
                  <div className="mt-2 flex flex-wrap gap-1.5" data-testid="detail-summary-chips">
                    {listing.price_total != null && <Chip>€{listing.price_total.toLocaleString('de-AT')}</Chip>}
                    {listing.area_m2 != null && <Chip>{listing.area_m2} m²</Chip>}
                    {listing.rooms != null && <Chip>{listing.rooms} rooms</Chip>}
                    {listing.bezirk && <Chip>{listing.bezirk}</Chip>}
                    {listing.ubahn_walk_minutes != null && <Chip>U-Bahn {listing.ubahn_walk_minutes} min</Chip>}
                  </div>
                </div>

                {/* Tab bar */}
                <div className="shrink-0 flex gap-1 border-b border-gray-200 px-4" role="tablist">
                  {tabs.filter((t) => t.show).map((t) => (
                    <button
                      key={t.key}
                      role="tab"
                      aria-selected={active === t.key}
                      data-testid={`tab-${t.key}`}
                      onClick={() => setTab(t.key)}
                      className={`px-3 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
                        active === t.key
                          ? 'border-accent text-gray-900'
                          : 'border-transparent text-gray-500 hover:text-gray-800'
                      }`}
                    >
                      {t.label}
                    </button>
                  ))}
                </div>

                {/* Scrollable active panel */}
                <div className="flex-1 overflow-y-auto p-6 space-y-4">
                  {active === 'overview' && (
                    <div data-testid="panel-overview" className="space-y-4">
                      {listing.image_url && !imageError ? (
                        <div className="relative w-full h-48 rounded-lg overflow-hidden bg-gray-100">
                          <img
                            src={listing.image_url}
                            alt={listing.title || 'Property image'}
                            className="w-full h-full object-cover"
                            onError={() => setImageError(true)}
                          />
                        </div>
                      ) : (
                        <div className="w-full h-48 rounded-lg bg-gray-100 flex items-center justify-center">
                          <span className="text-gray-400 text-sm">No image available</span>
                        </div>
                      )}

                      <div className="grid grid-cols-2 gap-4 text-sm">
                        {listing.price_total && (
                          <div><span className="font-medium">Price:</span> €{listing.price_total.toLocaleString('de-AT')}</div>
                        )}
                        {listing.area_m2 && <div><span className="font-medium">Area:</span> {listing.area_m2} m²</div>}
                        {listing.rooms && <div><span className="font-medium">Rooms:</span> {listing.rooms}</div>}
                        {listing.bezirk && <div><span className="font-medium">District:</span> {listing.bezirk}</div>}
                        {listing.year_built && <div><span className="font-medium">Year Built:</span> {listing.year_built}</div>}
                        {listing.floor && <div><span className="font-medium">Floor:</span> {listing.floor}</div>}
                        {listing.condition && <div><span className="font-medium">Condition:</span> {listing.condition}</div>}
                        {listing.heating && <div><span className="font-medium">Heating:</span> {listing.heating}</div>}
                        {listing.energy_class && <div><span className="font-medium">Energy Class:</span> {listing.energy_class}</div>}
                        {listing.hwb_value && <div><span className="font-medium">HWB:</span> {listing.hwb_value}</div>}
                        {listing.betriebskosten && <div><span className="font-medium">Betriebskosten:</span> €{listing.betriebskosten}</div>}
                        {listing.ubahn_walk_minutes != null && <div><span className="font-medium">U-Bahn:</span> {listing.ubahn_walk_minutes} min</div>}
                      </div>

                      <AddressBlock
                        address={listing.address}
                        bezirk={listing.bezirk}
                        coordinateSource={listing.coordinate_source}
                        coordinates={listing.coordinates ?? null}
                        destLat={destLat ? Number(destLat) : undefined}
                        destLon={destLon ? Number(destLon) : undefined}
                        destName={destName}
                        variant="detail"
                      />

                      {listing.infrastructure_distances && Object.keys(listing.infrastructure_distances).length > 0 && (
                        <div>
                          <h3 className="font-medium text-gray-700 mb-1">Infrastructure</h3>
                          <div className="text-sm text-gray-600">
                            {Object.entries(listing.infrastructure_distances).map(([k, v]) => (
                              <p key={k}>{k}: {String(v)}</p>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {active === 'financing' && (
                    <div data-testid="panel-financing" className="space-y-4">
                      <BankFinancingPanel priceTotal={listing.price_total} />

                      {listing.estimated_down_pct != null && (
                        <div className="border border-gray-200 rounded-lg p-4 bg-gray-50">
                          <h3 className="font-semibold text-gray-800 mb-3">Financing (estimated)</h3>
                          <div className="grid grid-cols-2 gap-2 text-sm">
                            <div>
                              <span className="font-medium text-gray-600">Standard (80% LTV):</span>
                              <span className="ml-2 font-semibold">
                                ~{Math.round(listing.estimated_down_pct)}%
                                {listing.estimated_equity_eur != null && (
                                  <span className="text-gray-500 font-normal">
                                    {' '}(~€{Math.round(listing.estimated_equity_eur / 1000)}k equity)
                                  </span>
                                )}
                              </span>
                            </div>
                            {listing.estimated_down_pct_kimv != null && (
                              <div>
                                <span className="font-medium text-gray-600">KIM-V (90% LTV):</span>
                                <span className="ml-2 font-semibold">
                                  ~{Math.round(listing.estimated_down_pct_kimv)}%
                                </span>
                              </div>
                            )}
                            {listing.belehnungswert_factor != null && (
                              <div>
                                <span className="font-medium text-gray-600">Belehnungswert est.:</span>
                                <span className="ml-2">~{Math.round(listing.belehnungswert_factor * 100)}% of asking</span>
                              </div>
                            )}
                            {listing.bank_score_confidence && (
                              <div>
                                <span className="font-medium text-gray-600">Confidence:</span>
                                <span className={`ml-2 ${
                                  listing.bank_score_confidence === 'high' ? 'text-green-700' :
                                  listing.bank_score_confidence === 'medium' ? 'text-yellow-700' :
                                  'text-gray-500'
                                }`}>
                                  {listing.bank_score_confidence}
                                </span>
                              </div>
                            )}
                            {listing.energy_class && (
                              <div className="col-span-2 text-xs text-gray-500 mt-1">
                                Based on: Energy {listing.energy_class}
                                {listing.hwb_value != null ? ` (HWB ${listing.hwb_value})` : ''}
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {active === 'investment' && (
                    <div data-testid="panel-investment" className="space-y-4">
                      <InvestmentMetricsPanel
                        priceTotal={listing.price_total}
                        areaM2={listing.area_m2}
                        bezirk={listing.bezirk}
                      />
                      <CommuteAndRentPanel listing={listing} />
                    </div>
                  )}

                  {active === 'area' && (
                    <div data-testid="panel-area" className="space-y-3">

                      {/* Price position hero */}
                      {zoneStats && zoneStats.this_listing.price_per_m2_vs_avg_pct != null && (
                        <div className={`rounded-xl p-4 border ${zoneStats.this_listing.price_per_m2_vs_avg_pct <= 0 ? 'bg-good-soft border-[#c4e5d6]' : 'bg-mid-soft border-[#ecd9b8]'}`}>
                          <div className="text-[10px] font-semibold uppercase tracking-widest text-ink-3 mb-2">
                            Price position · {zoneStats.district}
                          </div>
                          <div className="flex items-baseline gap-3">
                            <span className={`text-[38px] font-bold leading-none tabular-nums ${zoneStats.this_listing.price_per_m2_vs_avg_pct <= 0 ? 'text-good' : 'text-mid-ink'}`}>
                              {zoneStats.this_listing.price_per_m2_vs_avg_pct > 0 ? '+' : ''}{zoneStats.this_listing.price_per_m2_vs_avg_pct}%
                            </span>
                            <span className="text-[12px] text-ink-3 leading-snug">vs district<br/>avg €/m²</span>
                          </div>
                          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-[11.5px] text-ink-3">
                            {zoneStats.avg_price_per_m2 != null && (
                              <span>District avg <span className="font-semibold text-ink-2">€{zoneStats.avg_price_per_m2.toLocaleString('de-AT')}/m²</span></span>
                            )}
                            {zoneStats.this_listing.price_vs_avg_pct != null && (
                              <span>Total price <span className="font-semibold text-ink-2">{zoneStats.this_listing.price_vs_avg_pct > 0 ? '+' : ''}{zoneStats.this_listing.price_vs_avg_pct}% vs avg</span></span>
                            )}
                          </div>
                        </div>
                      )}

                      {/* Zone stat grid */}
                      {zoneStats && zoneStats.total_in_district > 0 && (
                        <div className="grid grid-cols-2 gap-2">
                          {([
                            { label: 'Listings in zone', value: String(zoneStats.total_in_district) },
                            { label: 'Avg district price', value: zoneStats.avg_price != null ? `€${Math.round(zoneStats.avg_price).toLocaleString('de-AT')}` : '—' },
                            { label: '≤ €500k options', value: zoneStats.matching_budget != null ? String(zoneStats.matching_budget) : '—' },
                            { label: 'Avg U-Bahn walk', value: zoneStats.avg_ubahn_minutes != null ? `${zoneStats.avg_ubahn_minutes} min` : '—' },
                          ] as { label: string; value: string }[]).map(({ label, value }) => (
                            <div key={label} className="rounded-lg border border-line bg-card p-3">
                              <div className="text-[10.5px] text-ink-3 mb-0.5">{label}</div>
                              <div className="text-[15px] font-semibold text-ink tabular-nums">{value}</div>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* District trend chart */}
                      {listing.bezirk && <DistrictTrendChart bezirk={listing.bezirk} />}

                      {/* Comparable listings */}
                      {comparables && comparables.length > 0 && (
                        <div className="pt-1" data-testid="comparables-section">
                          <h3 className="text-[11.5px] font-semibold text-ink mb-2">
                            Comparable listings
                            <span className="font-normal text-ink-3 ml-2">Same district · similar area &amp; price</span>
                          </h3>
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                            {comparables.map((c) => (
                              <a
                                key={c._id}
                                href={c.url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="flex gap-2.5 p-2.5 bg-card hover:bg-line rounded-xl border border-line transition-colors"
                              >
                                <div className="w-[52px] h-[52px] rounded-lg overflow-hidden bg-[#dde4ee] shrink-0 flex items-center justify-center">
                                  {c.image_url ? (
                                    <img src={c.image_url} alt="" className="w-full h-full object-cover" />
                                  ) : (
                                    <svg className="w-4 h-4 text-ink-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M3 11l9-7 9 7M5 10v10h14V10" />
                                    </svg>
                                  )}
                                </div>
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-baseline justify-between gap-1">
                                    <span className="font-bold text-[13px] text-ink">
                                      {c.price_total ? `€${c.price_total.toLocaleString('de-AT')}` : '—'}
                                    </span>
                                    {c.better_deal && (
                                      <span className="text-[9px] font-bold rounded-full px-1.5 py-0.5 bg-good-soft text-good">
                                        BETTER DEAL
                                      </span>
                                    )}
                                  </div>
                                  <p className="text-[11px] text-ink-2 line-clamp-1 mt-0.5">{c.title || 'Untitled'}</p>
                                  <p className="text-[10px] text-ink-3 mt-0.5 tabular-nums">
                                    {c.area_m2}m² · {c.rooms}rms · €{c.price_per_m2}/m²
                                    {c.score != null && <span className="ml-1 font-semibold text-ink-2">· {c.score}</span>}
                                  </p>
                                </div>
                              </a>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Sticky action footer — reachable from any tab */}
                <div className="shrink-0 border-t border-gray-200 px-6 py-3 flex items-center gap-3" data-testid="detail-actions">
                  <a
                    href={listing.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="px-4 py-2 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 transition-colors"
                  >
                    Open Original
                  </a>
                  <button
                    onClick={handleRecheck}
                    disabled={checking}
                    className="px-4 py-2 border border-gray-300 text-gray-700 text-sm rounded-lg hover:bg-gray-50 transition-colors disabled:opacity-50"
                  >
                    {checking ? 'Checking...' : 'Recheck Availability'}
                  </button>
                  {urlValid !== null && (
                    <span className={`px-3 py-2 text-sm rounded-lg ${urlValid ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}`}>
                      {urlValid ? 'Available' : 'Unavailable'}
                    </span>
                  )}
                </div>
              </>
            );
          })()
        ) : (
          <div className="p-8 text-center text-gray-500 relative">
            <button
              onClick={onClose}
              className="absolute top-3 right-4 text-gray-400 hover:text-gray-600 text-2xl leading-none"
            >
              &times;
            </button>
            Listing not found
          </div>
        )}
      </div>
    </div>
  );
}

function Chip({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-700">
      {children}
    </span>
  );
}
