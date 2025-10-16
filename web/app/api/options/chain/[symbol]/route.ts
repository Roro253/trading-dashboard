import { NextResponse } from 'next/server';
import { buildOptionsSummary } from 'server/services/options-summary';

export async function GET(
  _request: Request,
  context: { params: { symbol: string } },
) {
  const symbol = context.params.symbol.toUpperCase();

  try {
    const summary = await buildOptionsSummary(symbol);
    return NextResponse.json(summary);
  } catch (error) {
    if (process.env.NODE_ENV !== 'production') {
      // eslint-disable-next-line no-console
      console.error('options summary failed', error);
    }
    return NextResponse.json(
      {
        symbol,
        iv30: null,
        ivChangePctDoD: null,
        skew25d: null,
        topCallOI: null,
        topPutOI: null,
        asOf: new Date().toISOString(),
        takeaways: ['Not enough options data—will retry.'],
        evidence: [],
        source: 'polygon',
      },
      { status: 200 },
    );
  }
}
