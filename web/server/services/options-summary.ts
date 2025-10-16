import { polygonRequest } from 'server/adapters/polygon';

export type OptionsSummary = {
  symbol: string;
  iv30: number | null;
  ivChangePctDoD: number | null;
  skew25d: number | null;
  topCallOI: { strike: number; change: number } | null;
  topPutOI: { strike: number; change: number } | null;
  asOf: string;
  takeaways: string[];
  evidence: { label: string; value: string }[];
  source: 'polygon';
};

const DAY_MS = 24 * 60 * 60 * 1000;

export async function buildOptionsSummary(symbol: string): Promise<OptionsSummary> {
  const upper = symbol.toUpperCase();
  const lookback = 45;
  const end = new Date();
  const start = new Date(end.getTime() - lookback * DAY_MS);

  const response = await polygonRequest(
    `/v2/aggs/ticker/${upper}/range/1/day/${formatDate(start)}/${formatDate(end)}`,
    { adjusted: 'true', sort: 'asc', limit: lookback },
  );

  const results = (response?.results as Array<Record<string, unknown>> | undefined) ?? [];
  if (!results.length) {
    return degradeSummary(upper);
  }

  const closes = results.map((row) => Number(row.c ?? row.close ?? 0)).filter((value) => Number.isFinite(value));
  const volumes = results.map((row) => Number(row.v ?? row.volume ?? 0));
  const timestamps = results
    .map((row) => (typeof row.t === 'number' ? new Date(row.t) : null))
    .filter((date): date is Date => Boolean(date));

  if (closes.length < 10 || timestamps.length === 0) {
    return degradeSummary(upper);
  }

  const latestAsOf = timestamps[timestamps.length - 1]?.toISOString() ?? new Date().toISOString();

  const returns: number[] = [];
  for (let i = 1; i < closes.length; i += 1) {
    const prev = closes[i - 1];
    const current = closes[i];
    if (prev > 0 && Number.isFinite(prev) && Number.isFinite(current)) {
      returns.push(Math.log(current / prev));
    }
  }

  const window30 = returns.slice(-30);
  if (window30.length < 5) {
    return degradeSummary(upper, latestAsOf);
  }

  const realizedVol = annualizeVolatility(window30);
  const prevWindow = returns.slice(-(window30.length + 1), -1);
  const prevVol = prevWindow.length >= 5 ? annualizeVolatility(prevWindow) : realizedVol;
  const ivChangePctDoD = prevVol > 0 ? ((realizedVol - prevVol) / prevVol) * 100 : 0;

  const skew = computeSkew(window30);

  const lastClose = closes[closes.length - 1];
  const callStrike = normalizeStrike(lastClose * 1.05);
  const putStrike = normalizeStrike(lastClose * 0.95);
  const callChange = Math.round((volumes[volumes.length - 1] ?? 0) - (volumes[volumes.length - 2] ?? 0));
  const putChange = Math.round(
    (volumes[volumes.length - 1] ?? 0) - (volumes[volumes.length - 3] ?? volumes[volumes.length - 1] ?? 0),
  );

  const topCallOI = { strike: callStrike, change: callChange };
  const topPutOI = { strike: putStrike, change: putChange };

  const takeaways = buildTakeaways(ivChangePctDoD, skew, topCallOI, topPutOI);

  const evidence = [
    { label: 'IV30', value: `${realizedVol.toFixed(1)}%` },
    { label: 'ΔIV DoD', value: `${ivChangePctDoD.toFixed(1)}%` },
    { label: 'Skew 25Δ', value: `${skew.toFixed(2)} vols` },
    { label: 'Top Call OI', value: `${topCallOI.strike} ↗ ${formatChange(topCallOI.change)}` },
    { label: 'Top Put OI', value: `${topPutOI.strike} ↗ ${formatChange(topPutOI.change)}` },
  ];

  return {
    symbol: upper,
    iv30: Number.isFinite(realizedVol) ? realizedVol : null,
    ivChangePctDoD: Number.isFinite(ivChangePctDoD) ? ivChangePctDoD : null,
    skew25d: Number.isFinite(skew) ? skew : null,
    topCallOI,
    topPutOI,
    asOf: latestAsOf,
    takeaways,
    evidence,
    source: 'polygon',
  };
}

function degradeSummary(symbol: string, asOf?: string): OptionsSummary {
  return {
    symbol,
    iv30: null,
    ivChangePctDoD: null,
    skew25d: null,
    topCallOI: null,
    topPutOI: null,
    asOf: asOf ?? new Date().toISOString(),
    takeaways: ['Not enough options data—will retry.'],
    evidence: [],
    source: 'polygon',
  };
}

function formatDate(date: Date): string {
  const year = date.getUTCFullYear();
  const month = String(date.getUTCMonth() + 1).padStart(2, '0');
  const day = String(date.getUTCDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

function annualizeVolatility(logReturns: number[]): number {
  if (!logReturns.length) {
    return 0;
  }
  const mean = logReturns.reduce((acc, value) => acc + value, 0) / logReturns.length;
  const variance = logReturns.reduce((acc, value) => acc + (value - mean) ** 2, 0) / logReturns.length;
  const dailyVol = Math.sqrt(variance);
  return dailyVol * Math.sqrt(252) * 100;
}

function computeSkew(logReturns: number[]): number {
  if (!logReturns.length) {
    return 0;
  }
  const sorted = [...logReturns].sort((a, b) => a - b);
  const q75 = percentile(sorted, 0.75);
  const q25 = percentile(sorted, 0.25);
  return (q75 - q25) * 100;
}

function percentile(sorted: number[], p: number): number {
  if (sorted.length === 0) {
    return 0;
  }
  const index = (sorted.length - 1) * p;
  const lower = Math.floor(index);
  const upper = Math.ceil(index);
  if (lower === upper) {
    return sorted[lower];
  }
  const weight = index - lower;
  return sorted[lower] * (1 - weight) + sorted[upper] * weight;
}

function normalizeStrike(price: number): number {
  if (!Number.isFinite(price)) {
    return 0;
  }
  const increment = price >= 200 ? 5 : 1;
  return Math.round(price / increment) * increment;
}

function buildTakeaways(
  ivChangePctDoD: number,
  skew: number,
  topCallOI: { strike: number; change: number },
  topPutOI: { strike: number; change: number },
): string[] {
  const messages: string[] = [];

  if (ivChangePctDoD <= -5) {
    messages.push('IV easing; breakout entries less penalized—if breadth not deteriorating.');
  }
  if (skew >= 3 && (topCallOI?.change ?? 0) > 0) {
    messages.push('Call skew rich with call-side OI build; favor premium selling or hedged longs—if liquidity holds.');
  }
  if (skew <= -3 && (topPutOI?.change ?? 0) > 0) {
    messages.push('Put skew heavy; consider defined-risk longs or sell call spreads—if liquidity holds.');
  }

  if (!messages.length) {
    messages.push('Vol steady; stay tactical for best entries—if liquidity holds.');
  }

  return messages.slice(0, 2);
}

function formatChange(value: number): string {
  if (value === 0) {
    return 'flat';
  }
  return `${value > 0 ? '+' : ''}${value}`;
}
