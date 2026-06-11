import { NextRequest, NextResponse } from 'next/server';
import { getDb } from '@/lib/mongodb';

export const dynamic = 'force-dynamic';

const ENERGY_BASE: Record<string, number> = {
  'A++': 1.0, 'A+': 1.0, 'A': 0.97, 'B': 0.97, 'C': 0.92,
  'D': 0.85, 'E': 0.75, 'F': 0.65, 'G': 0.65,
};
const HWB_UPPER: Record<string, number> = {
  'A++': 25, 'A+': 25, 'A': 25, 'B': 50, 'C': 75, 'D': 100, 'E': 150,
};
const ENERGY_RE = /^[A-G][+]?[+]?$/;

function calcBankScore(l: Record<string, unknown>) {
  const energy_class = (l.energy_class as string | null) ?? null;
  const year_built = (l.year_built as number | null) ?? null;
  const facade_renovated = l.facade_renovated as boolean | null;
  const roof_renovated = l.roof_renovated as boolean | null;
  const window_type = l.window_type as string | null;
  const hwb_value = l.hwb_value as number | null;
  const condition = l.condition as string | null;
  const title = l.title as string | null;
  const price_total = l.price_total as number | null;

  const noneCount = [energy_class, year_built, facade_renovated, roof_renovated, window_type, hwb_value].filter((v) => v == null).length;
  const confidence = noneCount <= 2 ? 'high' : noneCount <= 4 ? 'medium' : 'low';

  let factor: number;
  const ec = energy_class && ENERGY_RE.test(energy_class) ? energy_class.toUpperCase() : null;
  if (ec && ENERGY_BASE[ec] != null) {
    factor = ENERGY_BASE[ec];
  } else if (year_built != null && year_built >= 2010) {
    factor = 0.95;
  } else if (year_built != null && year_built < 1970) {
    factor = 0.72;
  } else {
    factor = 0.82;
  }

  if (year_built != null) {
    if (year_built >= 2015) factor += 0.05;
    else if (year_built >= 2000) factor += 0.02;
    else if (year_built < 1970) factor -= 0.05;
  }
  if (facade_renovated === true) factor += 0.04;
  else if (facade_renovated === false) factor -= 0.03;
  if (roof_renovated === true) factor += 0.02;
  if (window_type === 'kastenfenster') factor -= 0.04;
  else if (window_type === 'kunststoff' || window_type === 'holz-alu' || window_type === 'isolierverglasung') factor += 0.02;

  if (ec && HWB_UPPER[ec] != null && hwb_value != null && hwb_value > HWB_UPPER[ec] * 0.7) {
    factor -= 0.03;
  }

  const text = `${condition ?? ''} ${title ?? ''}`.toLowerCase();
  let condPenalty = 0;
  if (text.includes('sanierungsbedürftig') || text.includes('renovierungsbedürftig')) condPenalty += 0.12;
  if (text.includes('ausbaupotential') || text.includes('ausbaumöglichkeit')) condPenalty += 0.09;
  if (text.includes('altbau') && !text.includes('renoviert')) condPenalty += 0.04;
  factor -= Math.min(condPenalty, 0.15);

  factor = Math.min(1, Math.round(factor * 10000) / 10000);

  if (!price_total || price_total <= 0) {
    return { belehnungswert_factor: factor, estimated_down_pct: null, estimated_down_pct_kimv: null, estimated_equity_eur: null, bank_score_confidence: confidence };
  }

  const downPct = Math.round((1 - 0.8 * factor) * 1000) / 10;
  const downPctKimv = Math.round((1 - 0.9 * factor) * 1000) / 10;
  const equityEur = Math.round(price_total * downPct / 100);

  return {
    belehnungswert_factor: factor,
    estimated_down_pct: downPct,
    estimated_down_pct_kimv: downPctKimv,
    estimated_equity_eur: equityEur,
    bank_score_confidence: confidence,
  };
}

export async function POST(request: NextRequest) {
  const url = new URL(request.url);
  const secret = url.searchParams.get('secret') ?? request.headers.get('x-admin-secret');
  if (secret !== (process.env.ADMIN_BACKFILL_SECRET ?? 'dev-backfill')) {
    return NextResponse.json({ error: 'Unauthorized' }, { status: 401 });
  }

  const dryRun = url.searchParams.get('dry_run') === 'true';
  const limit = Number(url.searchParams.get('limit') ?? '0');

  const db = getDb();
  if (!db) return NextResponse.json({ error: 'Database unavailable' }, { status: 503 });

  const query = { bank_score_confidence: { $exists: false } };
  const total = await db.collection('listings').countDocuments(query);
  const cursor = db.collection('listings').find(query, {
    projection: {
      _id: 1, energy_class: 1, year_built: 1, facade_renovated: 1, roof_renovated: 1,
      window_type: 1, hwb_value: 1, condition: 1, title: 1, price_total: 1,
    },
  });
  if (limit) cursor.limit(limit);

  let updated = 0;
  let failed = 0;
  const confDist: Record<string, number> = { high: 0, medium: 0, low: 0 };

  for await (const doc of cursor) {
    try {
      const score = calcBankScore(doc);
      if (dryRun) {
        // skip
      } else {
        await db.collection('listings').updateOne({ _id: doc._id }, { $set: score });
      }
      updated += 1;
      confDist[score.bank_score_confidence] += 1;
    } catch {
      failed += 1;
    }
  }

  return NextResponse.json({ dry_run: dryRun, total, updated, failed, confidence: confDist });
}
