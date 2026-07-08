import Link from 'next/link';
import { getDb } from '@/lib/mongodb';
import { ConfirmBanner } from '@/components/ConfirmBanner';

async function getStats() {
  try {
    const db = await getDb();
    if (!db) return { total: 200, withScore: 180 };
    const col = db.collection('listings');
    const total = await col.countDocuments({ url_is_valid: true, taken: { $ne: true } });
    const withScore = await col.countDocuments({ url_is_valid: true, taken: { $ne: true }, score: { $gt: 0 } });
    return { total, withScore };
  } catch {
    return { total: 200, withScore: 180 };
  }
}

export default async function LandingPage({
  searchParams,
}: {
  searchParams: Promise<{ confirmed?: string }>;
}) {
  const stats = await getStats();
  const { confirmed } = await searchParams;

  return (
    <div className="min-h-screen bg-white text-ink font-sans">
      <ConfirmBanner status={confirmed} />
      {/* Nav */}
      <nav className="sticky top-0 z-50 border-b border-line bg-white/90 backdrop-blur-sm">
        <div className="max-w-5xl mx-auto px-6 h-14 flex items-center justify-between">
          <span className="text-base font-bold tracking-tight text-ink">ImmoScouter</span>
          <div className="flex items-center gap-3">
            <Link
              href="/dashboard"
              className="text-sm font-medium text-ink-2 hover:text-ink transition-colors"
            >
              Browse listings
            </Link>
            <Link
              href="/dashboard"
              className="inline-flex items-center gap-1.5 bg-accent text-white text-sm font-semibold px-4 py-2 rounded-lg hover:opacity-90 transition-opacity"
            >
              Start free
            </Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="max-w-5xl mx-auto px-6 pt-20 pb-16 text-center">
        <div className="inline-flex items-center gap-2 bg-accent-soft text-accent text-xs font-semibold px-3 py-1.5 rounded-full mb-6">
          <span className="w-1.5 h-1.5 bg-accent rounded-full"></span>
          Vienna real estate · updated daily
        </div>
        <h1 className="text-4xl sm:text-5xl font-extrabold text-ink leading-tight mb-5">
          Find Vienna&apos;s best apartment<br className="hidden sm:block" /> deals before anyone else
        </h1>
        <p className="text-lg text-ink-2 max-w-xl mx-auto mb-8 leading-relaxed">
          AI-scored listings from Willhaben, ImmoKurier and DerStandard —
          ranked by your buyer profile, filtered by budget and commute. Free forever, with optional alerts.
        </p>
        <div className="flex flex-col sm:flex-row gap-3 justify-center">
          <Link
            href="/dashboard"
            className="inline-flex items-center justify-center gap-2 bg-accent text-white font-semibold px-7 py-3.5 rounded-xl text-base hover:opacity-90 transition-opacity shadow-lg shadow-accent/20"
          >
            Explore listings — it&apos;s free
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </Link>
          <Link
            href="/dashboard/map"
            className="inline-flex items-center justify-center gap-2 border border-line text-ink font-semibold px-7 py-3.5 rounded-xl text-base hover:bg-bg transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
            </svg>
            Open map view
          </Link>
        </div>
      </section>

      {/* Stats bar */}
      <section className="bg-bg border-y border-line">
        <div className="max-w-5xl mx-auto px-6 py-6 grid grid-cols-3 gap-4 text-center">
          <div>
            <div className="text-2xl font-bold text-ink">{stats.total}+</div>
            <div className="text-xs text-ink-2 mt-0.5">Active listings</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-ink">23</div>
            <div className="text-xs text-ink-2 mt-0.5">Vienna districts tracked</div>
          </div>
          <div>
            <div className="text-2xl font-bold text-ink">8</div>
            <div className="text-xs text-ink-2 mt-0.5">Buyer profiles</div>
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="max-w-5xl mx-auto px-6 py-20">
        <h2 className="text-2xl font-bold text-center text-ink mb-2">Everything you need to buy smarter</h2>
        <p className="text-center text-ink-2 mb-12 text-sm">No account required to start.</p>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {FEATURES.map((f) => (
            <div key={f.title} className="border border-line rounded-xl p-5 hover:shadow-sm transition-shadow">
              <div className="w-9 h-9 rounded-lg bg-accent-soft flex items-center justify-center mb-4 text-accent text-lg">
                {f.icon}
              </div>
              <h3 className="font-semibold text-ink mb-1.5">{f.title}</h3>
              <p className="text-sm text-ink-2 leading-relaxed">{f.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* How it works */}
      <section className="bg-bg border-y border-line">
        <div className="max-w-5xl mx-auto px-6 py-16">
          <h2 className="text-2xl font-bold text-center text-ink mb-12">How it works</h2>
          <div className="grid sm:grid-cols-3 gap-8">
            {STEPS.map((s, i) => (
              <div key={s.title} className="flex flex-col items-center text-center">
                <div className="w-10 h-10 rounded-full bg-accent text-white font-bold text-base flex items-center justify-center mb-4 shadow-md shadow-accent/30">
                  {i + 1}
                </div>
                <h3 className="font-semibold text-ink mb-2">{s.title}</h3>
                <p className="text-sm text-ink-2 leading-relaxed">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section className="max-w-5xl mx-auto px-6 py-20">
        <h2 className="text-2xl font-bold text-center text-ink mb-2">Simple pricing</h2>
        <p className="text-center text-ink-2 mb-12 text-sm">Start free. Upgrade when you need alerts.</p>
        <div className="grid sm:grid-cols-2 gap-6 max-w-2xl mx-auto">
          {/* Free */}
          <div className="border border-line rounded-2xl p-7 flex flex-col">
            <div className="text-sm font-semibold text-ink-2 mb-1">Free</div>
            <div className="text-3xl font-extrabold text-ink mb-1">€0</div>
            <div className="text-xs text-ink-2 mb-6">forever</div>
            <ul className="space-y-2.5 text-sm text-ink flex-1">
              {FREE_FEATURES.map((f) => (
                <li key={f} className="flex items-start gap-2">
                  <svg className="w-4 h-4 text-good shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                  </svg>
                  {f}
                </li>
              ))}
            </ul>
            <Link
              href="/dashboard"
              className="mt-7 w-full py-3 border border-line rounded-xl text-sm font-semibold text-ink text-center hover:bg-bg transition-colors"
            >
              Get started
            </Link>
          </div>

          {/* Pro */}
          <div className="border-2 border-accent rounded-2xl p-7 flex flex-col relative shadow-lg shadow-accent/10">
            <div className="absolute -top-3.5 left-1/2 -translate-x-1/2">
              <span className="bg-accent text-white text-xs font-bold px-3 py-1 rounded-full">Most popular</span>
            </div>
            <div className="text-sm font-semibold text-accent mb-1">Pro</div>
            <div className="text-3xl font-extrabold text-ink mb-1">€19</div>
            <div className="text-xs text-ink-2 mb-6">per month</div>
            <ul className="space-y-2.5 text-sm text-ink flex-1">
              {PRO_FEATURES.map((f) => (
                <li key={f} className="flex items-start gap-2">
                  <svg className="w-4 h-4 text-accent shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2.5} d="M5 13l4 4L19 7" />
                  </svg>
                  {f}
                </li>
              ))}
            </ul>
            <Link
              href="/dashboard"
              className="mt-7 w-full py-3 bg-accent text-white rounded-xl text-sm font-semibold text-center hover:opacity-90 transition-opacity"
            >
              Start free trial
            </Link>
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="bg-accent">
        <div className="max-w-5xl mx-auto px-6 py-16 text-center">
          <h2 className="text-2xl font-bold text-white mb-3">Ready to find your apartment?</h2>
          <p className="text-accent-soft/80 mb-7 text-sm">No sign-up needed. Start browsing in seconds.</p>
          <Link
            href="/dashboard"
            className="inline-flex items-center gap-2 bg-white text-accent font-bold px-8 py-3.5 rounded-xl text-base hover:bg-accent-soft transition-colors"
          >
            Browse listings now
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
          </Link>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-line">
        <div className="max-w-5xl mx-auto px-6 py-8 flex flex-col sm:flex-row justify-between items-center gap-3 text-xs text-ink-2">
          <span>© 2026 ImmoScouter · Vienna apartment search</span>
          <div className="flex gap-4">
            <Link href="/dashboard" className="hover:text-ink transition-colors">Dashboard</Link>
            <Link href="/dashboard/map" className="hover:text-ink transition-colors">Map</Link>
          </div>
        </div>
      </footer>
    </div>
  );
}

const FEATURES = [
  {
    icon: '🎯',
    title: 'AI scoring by buyer profile',
    desc: 'Every listing is scored for 8 buyer types — DIY renovator, growing family, urban professional and more. See what matters to you first.',
  },
  {
    icon: '🗺️',
    title: 'District price heatmap',
    desc: 'See which districts are above or below average price per m². Instantly spot where value still exists.',
  },
  {
    icon: '💶',
    title: 'Mortgage feasibility',
    desc: 'Enter your equity and interest rate. Each listing shows your monthly payment and whether a bank will finance it.',
  },
  {
    icon: '🔔',
    title: 'Email alerts (Pro)',
    desc: 'Get notified the moment a new listing matches your filters — instant, daily or weekly digest.',
  },
  {
    icon: '🚇',
    title: 'Commute filter',
    desc: 'Filter listings by walking distance to your workplace or a key destination. See only what fits your daily routine.',
  },
  {
    icon: '📊',
    title: 'Price vs zone average',
    desc: 'Filter for listings priced 10%, 15%, or 20% below their district average — the deals others miss.',
  },
];

const STEPS = [
  {
    title: 'Pick your buyer profile',
    desc: 'Choose from 8 personas that match your situation. The scoring engine re-weights every listing for your priorities.',
  },
  {
    title: 'Set your filters',
    desc: 'Max price, district, commute distance, mortgage affordability. Apply once, filters persist in your URL.',
  },
  {
    title: 'Get alerts on new matches',
    desc: 'Upgrade to Pro and never check manually again. Instant alerts land in your inbox as soon as a match is scraped.',
  },
];

const FREE_FEATURES = [
  'Browse top-scored listings',
  'Owner-occupier smart scoring',
  'District price heatmap',
  'Mortgage calculator',
  'Commute & price filters',
  'Interactive map (after sign-in)',
];

const PRO_FEATURES = [
  'Everything in Free',
  'All 5 buyer profiles — persona switching',
  'Email alerts (instant / daily / weekly)',
  'Unlimited saved searches',
  'Price vs zone average filter',
  'Priority support',
];
