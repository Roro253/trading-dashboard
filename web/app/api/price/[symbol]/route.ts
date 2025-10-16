import { NextResponse } from 'next/server';
import { getSnapshot, getPrevClose } from 'server/adapters/polygon';

const MAX_STALE_MS = 2 * 60_000;

function inferMarketStatus(asOf: string, fallback: boolean): 'open' | 'closed' | 'pre' | 'post' | 'unknown' {
  if (fallback) {
    return 'closed';
  }

  try {
    const date = new Date(asOf);
    if (Number.isNaN(date.getTime())) {
      return 'unknown';
    }

    const parts = new Intl.DateTimeFormat('en-US', {
      timeZone: 'America/New_York',
      hour: 'numeric',
      minute: 'numeric',
      hour12: false,
      weekday: 'short',
    }).formatToParts(date);

    const lookup = Object.fromEntries(parts.map((part) => [part.type, part.value]));
    const weekday = lookup.weekday ?? 'Mon';
    const hour = Number.parseInt(lookup.hour ?? '0', 10);
    const minute = Number.parseInt(lookup.minute ?? '0', 10);

    if (['Sat', 'Sun'].includes(weekday)) {
      return 'closed';
    }

    const minutes = hour * 60 + minute;
    if (minutes < 7 * 60) {
      return 'closed';
    }
    if (minutes < 9 * 60 + 30) {
      return 'pre';
    }
    if (minutes < 16 * 60) {
      return 'open';
    }
    if (minutes < 20 * 60) {
      return 'post';
    }
    return 'closed';
  } catch (error) {
    if (process.env.NODE_ENV !== 'production') {
      // eslint-disable-next-line no-console
      console.warn('market status inference failed', error);
    }
    return 'unknown';
  }
}

export async function GET(
  _request: Request,
  context: { params: { symbol: string } },
) {
  const symbol = context.params.symbol.toUpperCase();

  try {
    const snapshot = await getSnapshot(symbol);
    const now = Date.now();
    const asOfTime = new Date(snapshot.asOf).getTime();
    const staleByAge = Number.isFinite(asOfTime) && now - asOfTime > MAX_STALE_MS;

    const last = snapshot.last || snapshot.prevClose;
    const prevClose = snapshot.prevClose || snapshot.last;
    const changePct = prevClose ? (last - prevClose) / prevClose : 0;

    const stale = snapshot.stale || staleByAge;

    return NextResponse.json({
      symbol,
      last,
      prevClose,
      changePct,
      marketStatus: inferMarketStatus(snapshot.asOf, snapshot.fallback),
      asOf: snapshot.asOf,
      source: 'polygon',
      stale,
    });
  } catch (error) {
    if (process.env.NODE_ENV !== 'production') {
      // eslint-disable-next-line no-console
      console.error('price route failed, falling back to prev close', error);
    }
    const fallback = await getPrevClose(symbol);
    return NextResponse.json(
      {
        symbol,
        last: fallback.last,
        prevClose: fallback.prevClose,
        changePct: fallback.prevClose ? 0 : 0,
        marketStatus: 'closed',
        asOf: fallback.asOf,
        source: 'polygon',
        stale: true,
      },
      { status: 200 },
    );
  }
}
