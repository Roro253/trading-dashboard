import { NextResponse } from 'next/server';
import { fetchPcr } from 'server/services/pcr';

export async function GET() {
  try {
    const data = await fetchPcr();
    return NextResponse.json(data);
  } catch (error) {
    if (process.env.NODE_ENV !== 'production') {
      // eslint-disable-next-line no-console
      console.error('PCR route failed', error);
    }
    return NextResponse.json(
      {
        today: NaN,
        ma5: NaN,
        ma10: NaN,
        z10: 0,
        isExtremeHigh: false,
        isExtremeLow: false,
        takeaway: 'No PCR today.',
        asOf: new Date().toISOString(),
        source: 'cboe',
      },
      { status: 200 },
    );
  }
}
