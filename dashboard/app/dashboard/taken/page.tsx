'use client';

import React, { useState, useEffect } from 'react';

interface StatsSummary {
  summary: { total_active: number; total_taken: number; total: number; taken_rate_pct: number };
  by_source: { source: string; active: number; taken: number; taken_rate: number }[];
  by_district: { bezirk: string; active: number; taken: number; taken_rate: number }[];
  timing: { avg_days_active: number; min_days_active: number; max_days_active: number };
  price: { avg_price_active: number; avg_price_taken: number };
  price_alterations: { count_with_changes: number; examples: any[] };
}

interface TimelineEntry { date: string; count: number; }

interface TakenListing {
  _id: string;
  title: string;
  url: string;
  source_enum: string;
  bezirk: string;
  price_total: number;
  price_at_scrape: number;
  days_active: number;
  first_scraped_at: number;
  taken_at: string;
}

export default function TakenStatsPage() {
  const [summary, setSummary] = useState<StatsSummary | null>(null);
  const [timeline, setTimeline] = useState<{ created: TimelineEntry[]; taken: TimelineEntry[] }>({ created: [], taken: [] });
  const [takenListings, setTakenListings] = useState<TakenListing[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'overview' | 'list'>('overview');

  useEffect(() => {
    Promise.all([
      fetch('/api/stats/taken?days=30').then(r => r.json()),
      fetch('/api/stats/timeline?days=30').then(r => r.json()),
      fetch('/api/stats/taken-listings?limit=50').then(r => r.json())
    ]).then(([s, t, l]) => {
      setSummary(s);
      setTimeline(t);
      setTakenListings(l.listings || []);
      setLoading(false);
    });
  }, []);

  if (loading) return <div className="p-8 text-center">Laden...</div>;

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="mb-6">
          <h1 className="text-3xl font-bold text-gray-900">Taken Listings Analytics</h1>
          <p className="text-gray-600 mt-1">Track listing lifecycle: from scraped to offline</p>
        </div>

        <div className="grid grid-cols-4 gap-4 mb-6">
          <StatCard label="Total Active" value={summary?.summary.total_active ?? 0} color="blue" />
          <StatCard label="Total Taken" value={summary?.summary.total_taken ?? 0} color="red" />
          <StatCard label="Taken Rate" value={`${summary?.summary.taken_rate_pct ?? 0}%`} color="orange" />
          <StatCard label="Avg Days Active" value={summary?.timing.avg_days_active ?? 0} suffix="d" color="green" />
        </div>

        <div className="mb-6 flex gap-2">
          <button
            onClick={() => setActiveTab('overview')}
            className={`px-4 py-2 rounded ${activeTab === 'overview' ? 'bg-blue-600 text-white' : 'bg-white text-gray-700'}`}
          >
            Overview
          </button>
          <button
            onClick={() => setActiveTab('list')}
            className={`px-4 py-2 rounded ${activeTab === 'list' ? 'bg-blue-600 text-white' : 'bg-white text-gray-700'}`}
          >
            Taken Listings ({summary?.summary.total_taken ?? 0})
          </button>
        </div>

        {activeTab === 'overview' && (
          <div className="grid grid-cols-2 gap-6">
            <div className="bg-white rounded-lg shadow p-4">
              <h2 className="text-lg font-semibold mb-3">By Source</h2>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500">
                    <th>Source</th><th>Active</th><th>Taken</th><th>Rate</th>
                  </tr>
                </thead>
                <tbody>
                  {summary?.by_source.map(s => (
                    <tr key={s.source} className="border-t">
                      <td className="py-2">{s.source}</td>
                      <td>{s.active}</td>
                      <td className="text-red-600">{s.taken}</td>
                      <td>{s.taken_rate}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="bg-white rounded-lg shadow p-4">
              <h2 className="text-lg font-semibold mb-3">Timeline (Last 30 Days)</h2>
              <TimelineChart created={timeline.created} taken={timeline.taken} />
            </div>

            <div className="bg-white rounded-lg shadow p-4">
              <h2 className="text-lg font-semibold mb-3">By District</h2>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500">
                    <th>District</th><th>Active</th><th>Taken</th><th>Rate</th>
                  </tr>
                </thead>
                <tbody>
                  {summary?.by_district.filter(d => d.bezirk).map(d => (
                    <tr key={d.bezirk} className="border-t">
                      <td className="py-2">{d.bezirk}</td>
                      <td>{d.active}</td>
                      <td className="text-red-600">{d.taken}</td>
                      <td>{d.taken_rate}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="bg-white rounded-lg shadow p-4">
              <h2 className="text-lg font-semibold mb-3">Price Alterations</h2>
              <p className="text-sm text-gray-600 mb-2">
                {summary?.price_alterations.count_with_changes ?? 0} listings had price changes before being taken
              </p>
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500">
                    <th>Title</th><th>At Scrape</th><th>Last</th><th>Delta</th>
                  </tr>
                </thead>
                <tbody>
                  {summary?.price_alterations.examples.map((ex: any, i: number) => (
                    <tr key={i} className="border-t">
                      <td className="py-1 truncate max-w-xs">{ex.title}</td>
                      <td>€{(ex.price_at_scrape / 1000).toFixed(0)}k</td>
                      <td>€{(ex.last_price / 1000).toFixed(0)}k</td>
                      <td className={ex.delta < 0 ? 'text-red-600' : 'text-green-600'}>
                        {ex.delta > 0 ? '+' : ''}{(ex.delta / 1000).toFixed(0)}k
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {activeTab === 'list' && (
          <div className="bg-white rounded-lg shadow overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-gray-100">
                <tr className="text-left text-gray-600">
                  <th className="p-3">Title</th>
                  <th className="p-3">Source</th>
                  <th className="p-3">District</th>
                  <th className="p-3">Price</th>
                  <th className="p-3">Price at Scrape</th>
                  <th className="p-3">Days Active</th>
                  <th className="p-3">Taken At</th>
                </tr>
              </thead>
              <tbody>
                {takenListings.map(l => (
                  <tr key={l._id} className="border-t hover:bg-gray-50">
                    <td className="p-3 max-w-xs truncate">
                      <a href={l.url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline">
                        {l.title}
                      </a>
                    </td>
                    <td className="p-3">{l.source_enum}</td>
                    <td className="p-3">{l.bezirk}</td>
                    <td className="p-3">€{(l.price_total / 1000).toFixed(0)}k</td>
                    <td className="p-3">€{(l.price_at_scrape / 1000).toFixed(0)}k</td>
                    <td className="p-3">{l.days_active}d</td>
                    <td className="p-3 text-gray-500">{new Date(l.taken_at).toLocaleDateString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function StatCard({ label, value, color, suffix = '' }: { label: string; value: number | string; color: string; suffix?: string }) {
  const colors: Record<string, string> = {
    blue: 'bg-blue-50 text-blue-700 border-blue-200',
    red: 'bg-red-50 text-red-700 border-red-200',
    orange: 'bg-orange-50 text-orange-700 border-orange-200',
    green: 'bg-green-50 text-green-700 border-green-200',
  };
  return (
    <div className={`rounded-lg border p-4 ${colors[color]}`}>
      <p className="text-sm opacity-70">{label}</p>
      <p className="text-2xl font-bold">{value}{suffix}</p>
    </div>
  );
}

function TimelineChart({ created, taken }: { created: TimelineEntry[]; taken: TimelineEntry[] }) {
  if (created.length === 0 && taken.length === 0) {
    return <p className="text-sm text-gray-500 text-center py-8">No data yet</p>;
  }
  const maxCount = Math.max(
    ...created.map(c => c.count),
    ...taken.map(t => t.count),
    1
  );
  return (
    <div className="flex items-end gap-1 h-32">
      {created.slice(-14).map((c, i) => (
        <div key={i} className="flex-1 flex flex-col gap-0.5">
          <div className="bg-blue-400 rounded-t" style={{ height: `${(c.count / maxCount) * 100}%`, minHeight: '2px' }} title={`Created: ${c.count}`} />
          <div className="bg-red-400 rounded-t" style={{ height: `${(taken.find(t => t.date === c.date)?.count || 0) / maxCount * 100}%`, minHeight: '2px' }} title={`Taken: ${taken.find(t => t.date === c.date)?.count || 0}`} />
        </div>
      ))}
      <div className="flex gap-2 mt-1 text-xs text-gray-500">
        <span className="flex items-center gap-1"><span className="w-2 h-2 bg-blue-400 rounded" /> Created</span>
        <span className="flex items-center gap-1"><span className="w-2 h-2 bg-red-400 rounded" /> Taken</span>
      </div>
    </div>
  );
}