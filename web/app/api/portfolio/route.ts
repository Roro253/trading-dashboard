import { NextResponse } from 'next/server';

// Mock portfolio data endpoint
export async function GET() {
  try {
    const mockData = {
      portfolio: {
        totalValue: 91136.40,
        dayChange: 516.55,
        dayChangePercent: 0.57,
        totalReturn: 4236.40,
        totalReturnPercent: 4.87
      },
      positions: [
        {
          symbol: 'SPY',
          shares: 100,
          value: 42850.00,
          dayChange: 428.50,
          dayChangePercent: 1.01,
          avgCost: 415.25,
          marketPrice: 428.50
        },
        {
          symbol: 'QQQ',
          shares: 50,
          value: 18925.50,
          dayChange: -89.25,
          dayChangePercent: -0.47,
          avgCost: 365.80,
          marketPrice: 378.51
        },
        {
          symbol: 'NVDA',
          shares: 25,
          value: 21875.00,
          dayChange: 312.50,
          dayChangePercent: 1.45,
          avgCost: 825.00,
          marketPrice: 875.00
        },
        {
          symbol: 'TSLA',
          shares: 30,
          value: 7485.90,
          dayChange: -134.70,
          dayChangePercent: -1.77,
          avgCost: 245.80,
          marketPrice: 249.53
        }
      ]
    };

    return NextResponse.json(mockData);
  } catch (error) {
    console.error('Portfolio API error:', error);
    return NextResponse.json(
      { error: 'Failed to fetch portfolio data' },
      { status: 500 }
    );
  }
}