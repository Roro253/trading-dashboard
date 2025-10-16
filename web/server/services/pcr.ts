const CBOE_PCR_URL = 'https://cdn.cboe.com/api/global/us_indices/pc_ratio/pc_ratio.json';
const CACHE_TTL_MS = 15 * 60_000;

export type PcrResponse = {
  today: number;
  ma5: number;
  ma10: number;
  z10: number;
  isExtremeHigh: boolean;
  isExtremeLow: boolean;
  takeaway: string;
  asOf: string;
  source: 'cboe';
};

type RawPcrRow = {
  date: string;
  total_pcr: string;
  equity_pcr: string;
};

let cached: { data: PcrResponse; expiresAt: number } | null = null;

export async function fetchPcr(): Promise<PcrResponse> {
  const now = Date.now();
  if (cached && cached.expiresAt > now) {
    return cached.data;
  }

  const response = await fetch(CBOE_PCR_URL, {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
    cache: 'no-store',
  });

  if (!response.ok) {
    throw new Error(`Failed to fetch PCR data: ${response.status}`);
  }

  const payload = (await response.json()) as { data: RawPcrRow[] };
  const rows = payload?.data ?? [];
  if (!rows.length) {
    throw new Error('PCR payload empty');
  }

  const parsed = rows
    .map((row) => ({
      date: row.date,
      equity: Number.parseFloat(row.equity_pcr),
      total: Number.parseFloat(row.total_pcr),
    }))
    .filter((row) => Number.isFinite(row.equity));

  if (!parsed.length) {
    throw new Error('PCR equity series empty');
  }

  parsed.sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
  const latest = parsed[parsed.length - 1];
  const last10 = parsed.slice(-10);
  const last5 = parsed.slice(-5);

  const ma5 = average(last5.map((row) => row.equity));
  const ma10 = average(last10.map((row) => row.equity));
  const z10 = computeZScore(latest.equity, last10.map((row) => row.equity));

  const max10 = Math.max(...last10.map((row) => row.equity));
  const min10 = Math.min(...last10.map((row) => row.equity));

  const isExtremeHigh = latest.equity >= max10 && latest.equity >= 1.1;
  const isExtremeLow = latest.equity <= min10 && latest.equity <= 0.8;

  const takeaway = buildTakeaway({ today: latest.equity, isExtremeHigh, isExtremeLow });

  const result: PcrResponse = {
    today: Number(latest.equity.toFixed(3)),
    ma5: Number(ma5.toFixed(3)),
    ma10: Number(ma10.toFixed(3)),
    z10: Number(z10.toFixed(2)),
    isExtremeHigh,
    isExtremeLow,
    takeaway,
    asOf: new Date(latest.date).toISOString(),
    source: 'cboe',
  };

  cached = { data: result, expiresAt: now + CACHE_TTL_MS };

  return result;
}

function average(values: number[]): number {
  if (!values.length) {
    return 0;
  }
  const sum = values.reduce((acc, value) => acc + value, 0);
  return sum / values.length;
}

function computeZScore(latest: number, series: number[]): number {
  if (!series.length) {
    return 0;
  }
  const mean = average(series);
  const variance = average(series.map((value) => (value - mean) ** 2));
  const stdDev = Math.sqrt(variance);
  if (stdDev === 0) {
    return 0;
  }
  return (latest - mean) / stdDev;
}

function buildTakeaway(params: { today: number; isExtremeHigh: boolean; isExtremeLow: boolean }): string {
  if (params.isExtremeHigh) {
    return 'Crowd hedging aggressively; contrarian bullish into next session if breadth stabilizes.';
  }
  if (params.isExtremeLow) {
    return 'Call-chasing; vulnerable to pullback without new highs.';
  }
  return 'Neutral; monitor skew/breadth for confirmation.';
}
