'use client';

import React, { useState, useCallback, useEffect, useMemo, Suspense } from 'react';
import { useSearchParams, useRouter, usePathname } from 'next/navigation';
import { ListingCard } from '@/components/ListingCard';
import { FilterBar, SortOption } from '@/components/FilterBar';
import { FilterDrawer } from '@/components/FilterDrawer';
import { ListingDetail } from '@/components/ListingDetail';
import { ProfileSelector } from '@/components/ProfileSelector';
import { SmartInsightsPanel } from '@/components/SmartInsightsPanel';
import { SaveSearchButton } from '@/components/SaveSearchButton';
import { EmailAlertsModal } from '@/components/EmailAlertsModal';
import { PaywallModal } from '@/components/PaywallModal';
import { ListingBase } from '@/lib/types';
import { useFilters } from '@/lib/useFilters';
import { DEFAULT_PROFILE } from '@/lib/profile';

function calcMonatsrate(loanAmount: number, rate: number): number {
  if (loanAmount <= 0 || rate <= 0) return 0;
  const r = rate / 100 / 12;
  const n = 30 * 12;
  if (r === 0) return loanAmount / n;
  return loanAmount * (r * Math.pow(1 + r, n)) / (Math.pow(1 + r, n) - 1);
}

function DashboardContent() {
  const searchParams = useSearchParams();
  const {
    minScore, district, sortBy, maxPrice, showUnfinanceable,
    equity, rate, maxEquity, profile, belowAvgPct,
    destName, destLat, destLon, maxCommute,
    update,
  } = useFilters();

  const [listings, setListings] = useState<ListingBase[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filterDrawerOpen, setFilterDrawerOpen] = useState(false);
  const [alertsOpen, setAlertsOpen] = useState(false);
  const [profilePaywall, setProfilePaywall] = useState(false);
  const [scoresById, setScoresById] = useState<Record<string, Record<string, number | null>>>({});

  const fetchListings = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (minScore !== '0') params.set('min_score', minScore);
      if (district) params.set('district', district);
      params.set('sort', sortBy);
      if (profile !== DEFAULT_PROFILE) params.set('profile', profile);
      if (maxPrice && maxPrice !== '500000') params.set('max_price', maxPrice);
      if (maxEquity) params.set('max_equity', maxEquity);
      if (belowAvgPct) params.set('below_avg_pct', belowAvgPct);

      const res = await fetch(`/api/listings/top?${params.toString()}`);
      if (res.status === 402) {
        // Free tier picked a Pro persona — show paywall, fall back to default
        setProfilePaywall(true);
        update({ profile: DEFAULT_PROFILE });
        return;
      }
      const data = await res.json();
      const items = (data.listings ?? []) as Array<ListingBase & { scores?: Record<string, number | null> | null }>;
      setListings(items);
      const map: Record<string, Record<string, number | null>> = {};
      for (const l of items) {
        map[l._id] = (l.scores && typeof l.scores === 'object') ? l.scores : { [profile]: l.score ?? null };
      }
      setScoresById(map);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [minScore, district, sortBy, profile, maxPrice, maxEquity, belowAvgPct, update]);

  useEffect(() => { fetchListings(); }, [fetchListings]);

  // Re-sort locally when profile changes (no network call)
  useEffect(() => {
    if (Object.keys(scoresById).length === 0) return;
    setListings((prev) => {
      const sorted = [...prev].sort((a, b) => {
        const sa = scoresById[a._id]?.[profile] ?? a.score ?? 0;
        const sb = scoresById[b._id]?.[profile] ?? b.score ?? 0;
        return sb - sa;
      });
      return sorted;
    });
  }, [profile, scoresById]);

  const equityNum = Number(equity) || 100000;
  const rateNum = Number(rate) || 3.8;

  const enrichedListings = useMemo(() => {
    return listings.map((l) => {
      if (l.price_total == null || l.price_total <= 0) return l;
      const downPct = l.estimated_down_pct ?? 20;
      const bankLtv = 1 - downPct / 100;
      const loanAmount = l.price_total * bankLtv;
      const monatsrate = Math.round(calcMonatsrate(loanAmount, rateNum));
      const taxAmount = Math.round(l.price_total * 0.11);
      const cashNeeded = Math.round(l.price_total * (downPct / 100 + 0.11));
      return {
        ...l,
        monatsrate,
        cashNeeded,
      };
    });
  }, [listings, rateNum]);

  const filteredListings = useMemo(() => {
    const maxPriceNum = maxPrice ? Number(maxPrice) : null;
    const maxEquityNum = maxEquity ? Number(maxEquity) : null;
    const belowAvgNum = belowAvgPct ? Number(belowAvgPct) : null;
    const maxCommuteNum = maxCommute ? Number(maxCommute) : null;
    const destLatNum = destLat ? Number(destLat) : null;
    const destLonNum = destLon ? Number(destLon) : null;
    const WALK_KMH = 4.8;
    function haversineKm(a: { lat: number; lon: number }, b: { lat: number; lon: number }): number {
      const R = 6371;
      const dLat = (b.lat - a.lat) * Math.PI / 180;
      const dLon = (b.lon - a.lon) * Math.PI / 180;
      const lat1 = a.lat * Math.PI / 180;
      const lat2 = b.lat * Math.PI / 180;
      const x = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
      return 2 * R * Math.asin(Math.sqrt(x));
    }
    return enrichedListings.filter((l) => {
      if (maxPriceNum != null && Number.isFinite(maxPriceNum) && l.price_total != null && l.price_total > maxPriceNum) return false;
      if (maxEquityNum != null && Number.isFinite(maxEquityNum) && l.estimated_equity_eur != null && l.estimated_equity_eur > maxEquityNum) return false;
      if (
        !showUnfinanceable &&
        l.estimated_down_pct != null &&
        l.estimated_down_pct > 30 &&
        l.bank_score_confidence !== 'low'
      ) return false;
      if (belowAvgNum != null && Number.isFinite(belowAvgNum)) {
        const lAvg = (l as ListingBase & { price_vs_avg_pct?: number | null }).price_vs_avg_pct;
        if (lAvg == null || lAvg > -belowAvgNum) return false;
      }
      if (maxCommuteNum != null && Number.isFinite(maxCommuteNum) && destLatNum != null && destLonNum != null) {
        const lcoords = (l as ListingBase & { coordinates?: { lat: number; lon: number } | null }).coordinates;
        if (lcoords) {
          const km = haversineKm(lcoords, { lat: destLatNum, lon: destLonNum });
          const walkMin = Math.round((km / WALK_KMH) * 60);
          if (walkMin > maxCommuteNum) return false;
        }
      }
      return true;
    });
  }, [enrichedListings, maxPrice, showUnfinanceable, maxEquity, belowAvgPct, maxCommute, destLat, destLon]);

  return (
    <main className="min-h-screen bg-gray-50 p-6 pb-24 md:pb-6">
      <div className="max-w-6xl mx-auto">
        <header className="mb-4 flex items-start justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Top Property Picks</h1>
            <p className="text-sm text-gray-500 mt-1">
              {filteredListings.length} listing{filteredListings.length === 1 ? '' : 's'} matching your filters
            </p>
          </div>
          <div className="flex items-center gap-2">
            <ProfileSelector value={profile} onChange={(v) => update({ profile: v })} />
            <SaveSearchButton />
            <button
              type="button"
              onClick={() => setAlertsOpen(true)}
              className="inline-flex items-center gap-1.5 rounded-md border border-border bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 hover:border-muted transition-colors"
              data-testid="open-alerts"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9"/></svg>
              Email alerts
            </button>
            <a
              href={`/dashboard/map${searchParams.toString() ? `?${searchParams.toString()}` : ''}`}
              className="inline-flex items-center gap-1.5 rounded-md border border-border bg-white px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50 hover:border-muted transition-colors"
              data-testid="open-map"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
              </svg>
              Map view
            </a>
          </div>
        </header>

        <SmartInsightsPanel />

        {/* Desktop-only filter bar */}
        <div className="hidden md:block">
          <FilterBar
            minScore={minScore}
            onMinScoreChange={(v) => update({ minScore: v })}
            district={district}
            onDistrictChange={(v) => update({ district: v })}
            onRefresh={fetchListings}
            sortBy={sortBy}
            onSortChange={(v) => update({ sortBy: v })}
            maxPrice={maxPrice}
            onMaxPriceChange={(v) => update({ maxPrice: v })}
            showUnfinanceable={showUnfinanceable}
            onShowUnfinanceableChange={(v) => update({ showUnfinanceable: v })}
            equity={equity}
            onEquityChange={(v) => update({ equity: v })}
            rate={rate}
            onRateChange={(v) => update({ rate: v })}
            maxEquity={maxEquity}
            onMaxEquityChange={(v) => update({ maxEquity: v })}
            belowAvgPct={belowAvgPct}
            onBelowAvgPctChange={(v) => update({ belowAvgPct: v })}
            destName={destName}
            maxCommute={maxCommute}
            onDestChange={(name, lat, lon) => update({ destName: name, destLat: lat, destLon: lon })}
            onMaxCommuteChange={(v) => update({ maxCommute: v })}
          />
        </div>

        {loading ? (
          <p className="text-gray-500">Loading...</p>
        ) : filteredListings.length === 0 ? (
          <p className="text-gray-400">{listings.length === 0 ? 'No listings found.' : 'All listings filtered out.'}</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredListings.map((l) => (
              <ListingCard key={l._id} listing={l} onClick={setSelectedId} destLat={destLat ? Number(destLat) : undefined} destLon={destLon ? Number(destLon) : undefined} destName={destName || undefined} />
            ))}
          </div>
        )}
      </div>

      {/* Mobile filter FAB */}
      <button
        onClick={() => setFilterDrawerOpen(true)}
        className="md:hidden fixed bottom-6 right-6 w-14 h-14 rounded-full bg-accent text-white shadow-lg flex items-center justify-center z-50 hover:opacity-90 transition-opacity"
        aria-label="Open filters"
      >
        <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 4a1 1 0 011-1h16a1 1 0 011 1v2.586a1 1 0 01-.293.707l-6.414 6.414a1 1 0 00-.293.707V17l-4 4v-6.586a1 1 0 00-.293-.707L3.293 7.293A1 1 0 013 6.586V4z" />
        </svg>
      </button>

      {/* Filter drawer modal */}
      <FilterDrawer
        open={filterDrawerOpen}
        onClose={() => setFilterDrawerOpen(false)}
        profile={profile}
        onProfileChange={(v) => update({ profile: v })}
        minScore={minScore}
        onMinScoreChange={(v) => update({ minScore: v })}
        district={district}
        onDistrictChange={(v) => update({ district: v })}
        onRefresh={fetchListings}
        sortBy={sortBy}
        onSortChange={(v) => update({ sortBy: v })}
        maxPrice={maxPrice}
        onMaxPriceChange={(v) => update({ maxPrice: v })}
        showUnfinanceable={showUnfinanceable}
        onShowUnfinanceableChange={(v) => update({ showUnfinanceable: v })}
        equity={equity}
        onEquityChange={(v) => update({ equity: v })}
        rate={rate}
        onRateChange={(v) => update({ rate: v })}
      />

      <PaywallModal open={profilePaywall} reason="pro_profiles" onClose={() => setProfilePaywall(false)} />

      {selectedId && (
        <ListingDetail
          id={selectedId}
          onClose={() => setSelectedId(null)}
        />
      )}

      <EmailAlertsModal open={alertsOpen} onClose={() => setAlertsOpen(false)} />
    </main>
  );
}

export default function DashboardPage() {
  return (
    <Suspense fallback={<div className="p-6 text-gray-500">Loading...</div>}>
      <DashboardContent />
    </Suspense>
  );
}
