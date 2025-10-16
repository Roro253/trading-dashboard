const POLYGON_BASE_URL = 'https://api.polygon.io';
const CACHE_TTL_MS = 60_000;
const CIRCUIT_BREAKER_THRESHOLD = 3;
const CIRCUIT_BREAKER_COOLDOWN_MS = 5 * 60_000;

export type PolygonPriceSnapshot = {
  last: number;
  prevClose: number;
  changePct: number;
  asOf: string;
  latencyMs: number;
  stale: boolean;
  fallback: boolean;
};

type CachedEntry = {
  value: PolygonPriceSnapshot;
  fetchedAt: number;
  expiresAt: number;
  stale: boolean;
  fallback: boolean;
};

type SymbolState = {
  failures: number;
  circuitOpenedAt: number | null;
  circuitUntil: number | null;
};

const snapshotCache = new Map<string, CachedEntry>();
const prevCloseCache = new Map<string, CachedEntry>();
const revalidationPromises = new Map<string, Promise<void>>();
const symbolState = new Map<string, SymbolState>();

export function getPolygonHealth() {
  return Array.from(symbolState.entries()).reduce<Record<string, { circuitOpen: boolean; failures: number }>>(
    (acc, [symbol, state]) => {
      const now = Date.now();
      const circuitOpen = (state.circuitUntil ?? 0) > now;
      acc[symbol] = { circuitOpen, failures: state.failures };
      return acc;
    },
    {},
  );
}

export async function getPrevClose(symbol: string): Promise<PolygonPriceSnapshot> {
  const upper = symbol.toUpperCase();
  const cached = ensureFreshCache(prevCloseCache, upper);
  if (cached) {
    if (cached.expiresAt <= Date.now()) {
      triggerRevalidation(prevCloseCache, upper, 'prevClose', () => fetchPrevClose(upper));
      cached.value = { ...cached.value, stale: true };
    }
    return cached.value;
  }

  const snapshot = await fetchPrevClose(upper);
  updateCache(prevCloseCache, upper, snapshot, { fallback: false });
  return snapshot;
}

export async function getSnapshot(symbol: string): Promise<PolygonPriceSnapshot> {
  const upper = symbol.toUpperCase();
  const state = getOrCreateSymbolState(upper);
  const now = Date.now();
  const breakerOpen = (state.circuitUntil ?? 0) > now;

  if (breakerOpen) {
    const fallback = await getPrevClose(upper);
    const staleFallback = {
      ...fallback,
      latencyMs: 0,
      stale: true,
      fallback: true,
    };
    updateCache(snapshotCache, upper, staleFallback, { fallback: true });
    return staleFallback;
  }

  const cached = ensureFreshCache(snapshotCache, upper);
  if (cached) {
    const stale = cached.expiresAt <= now;
    if (stale) {
      triggerRevalidation(snapshotCache, upper, 'snapshot', () => fetchSnapshot(upper));
      cached.value = { ...cached.value, stale: true };
    }
    return cached.value;
  }

  try {
    const snapshot = await fetchSnapshot(upper);
    updateCache(snapshotCache, upper, snapshot, { fallback: false });
    resetFailures(upper);
    return snapshot;
  } catch (error) {
    recordFailure(upper, error);
    const fallback = await getPrevClose(upper);
    const staleFallback = {
      ...fallback,
      latencyMs: 0,
      stale: true,
      fallback: true,
    };
    updateCache(snapshotCache, upper, staleFallback, { fallback: true });
    return staleFallback;
  }
}

function ensureFreshCache(cache: Map<string, CachedEntry>, symbol: string): CachedEntry | undefined {
  const entry = cache.get(symbol);
  if (!entry) {
    return undefined;
  }
  if (entry.expiresAt <= Date.now()) {
    entry.stale = true;
    entry.value = { ...entry.value, stale: true };
  } else {
    entry.stale = entry.value.fallback;
    entry.value = { ...entry.value, stale: entry.value.fallback };
  }
  return entry;
}

function updateCache(
  cache: Map<string, CachedEntry>,
  symbol: string,
  value: PolygonPriceSnapshot,
  options: { fallback: boolean },
) {
  cache.set(symbol, {
    value,
    fetchedAt: Date.now(),
    expiresAt: Date.now() + CACHE_TTL_MS,
    stale: false,
    fallback: options.fallback,
  });
}

function triggerRevalidation(
  cache: Map<string, CachedEntry>,
  symbol: string,
  namespace: 'snapshot' | 'prevClose',
  revalidate: () => Promise<PolygonPriceSnapshot>,
) {
  const key = `${namespace}:${symbol}`;
  if (revalidationPromises.has(key)) {
    return;
  }

  const promise = revalidate()
    .then((result) => {
      updateCache(cache, symbol, result, { fallback: result.fallback });
      if (namespace === 'snapshot' && !result.fallback) {
        resetFailures(symbol);
      }
    })
    .catch((error) => {
      if (namespace === 'snapshot') {
        recordFailure(symbol, error);
      }
    })
    .finally(() => {
      revalidationPromises.delete(key);
    });

  revalidationPromises.set(key, promise);
}

async function fetchPrevClose(symbol: string): Promise<PolygonPriceSnapshot> {
  const start = Date.now();
  const payload = await polygonRequest(`/v2/aggs/ticker/${symbol}/prev`, { adjusted: 'true' });

  const closeResult = payload?.results?.[0] as Record<string, unknown> | undefined;
  if (closeResult) {
    const prevClose = Number((closeResult.c as number | undefined) ?? (closeResult.close as number | undefined) ?? 0);
    const asOfValue = closeResult.t as number | undefined;
    const asOf = typeof asOfValue === 'number' ? new Date(asOfValue).toISOString() : new Date().toISOString();
    return {
      last: prevClose,
      prevClose,
      changePct: 0,
      asOf,
      latencyMs: Date.now() - start,
      stale: false,
      fallback: false,
    };
  }

  return {
    last: 0,
    prevClose: 0,
    changePct: 0,
    asOf: new Date().toISOString(),
    latencyMs: Date.now() - start,
    stale: true,
    fallback: true,
  };
}

async function fetchSnapshot(symbol: string): Promise<PolygonPriceSnapshot> {
  const start = Date.now();
  const payload = await polygonRequest(`/v2/snapshot/locale/us/markets/stocks/tickers/${symbol}`);

  const ticker = payload?.ticker as Record<string, any> | undefined;
  if (!ticker) {
    throw new Error(`Snapshot missing ticker payload for ${symbol}`);
  }

  const lastPrice =
    Number(ticker.lastTrade?.p ?? ticker.lastQuote?.p ?? ticker.day?.close ?? ticker.prevDay?.close ?? NaN) || 0;
  const prevClose = Number(ticker.prevDay?.close ?? ticker.day?.close ?? lastPrice) || 0;
  const tradeTs = ticker.lastTrade?.t as number | undefined;
  const asOf = typeof tradeTs === 'number' ? new Date(tradeTs).toISOString() : new Date().toISOString();
  const changePct = prevClose ? (lastPrice - prevClose) / prevClose : 0;

  return {
    last: lastPrice,
    prevClose,
    changePct,
    asOf,
    latencyMs: Date.now() - start,
    stale: false,
    fallback: false,
  };
}

async function polygonRequest(path: string, params: Record<string, string | number | boolean> = {}) {
  const apiKey = getPolygonApiKey();
  const url = new URL(`${POLYGON_BASE_URL}${path}`);
  url.searchParams.set('apiKey', apiKey);
  for (const [key, value] of Object.entries(params)) {
    url.searchParams.set(key, String(value));
  }

  const response = await fetch(url.toString(), {
    method: 'GET',
    headers: {
      Accept: 'application/json',
    },
    cache: 'no-store',
  });

  if (!response.ok) {
    throw new Error(`Polygon request failed: ${response.status} ${response.statusText}`);
  }

  return (await response.json()) as Record<string, unknown>;
}

function getPolygonApiKey(): string {
  const fallbackKey = 'JlAQap9qJ8F8VrfChiPmYpticVo6SMPO';
  const key = process.env.POLYGON_API_KEY ?? fallbackKey;
  if (!key) {
    throw new Error('POLYGON_API_KEY is not configured');
  }
  return key;
}

function getOrCreateSymbolState(symbol: string): SymbolState {
  let state = symbolState.get(symbol);
  if (!state) {
    state = { failures: 0, circuitOpenedAt: null, circuitUntil: null };
    symbolState.set(symbol, state);
  }
  return state;
}

function resetFailures(symbol: string) {
  const state = getOrCreateSymbolState(symbol);
  state.failures = 0;
  state.circuitOpenedAt = null;
  state.circuitUntil = null;
}

function recordFailure(symbol: string, error: unknown) {
  const state = getOrCreateSymbolState(symbol);
  state.failures += 1;

  if (state.failures >= CIRCUIT_BREAKER_THRESHOLD) {
    state.circuitOpenedAt = Date.now();
    state.circuitUntil = state.circuitOpenedAt + CIRCUIT_BREAKER_COOLDOWN_MS;
  }

  if (process.env.NODE_ENV !== 'production') {
    // eslint-disable-next-line no-console
    console.warn(`Polygon adapter failure for ${symbol}:`, error);
  }
}
