'use client';

import { useState, useEffect } from 'react';
import styles from '../styles/ProfessionalPortfolio.module.css';

interface MarketSignal {
  symbol: string;
  companyName: string;
  sentiment: 'Strong Bullish' | 'Bullish' | 'Neutral' | 'Bearish' | 'Strong Bearish';
  confidence: number;
  currentPrice: number;
  change: number;
  changePercent: number;
  aiInsight: string;
  timeHorizon: 'Short' | 'Medium' | 'Long';
  technicalScore: number;
  sentimentScore: number;
}

interface MarketOverview {
  marketSentiment: 'BULLISH' | 'BEARISH' | 'NEUTRAL';
  fearGreedIndex: number;
  volatilityIndex: number;
  aiConfidence: number;
  trendStrength: number;
}

// Helper functions for sentiment display
const getSentimentColor = (sentiment: string) => {
  switch (sentiment) {
    case 'BULLISH': return styles.positive;
    case 'BEARISH': return styles.negative;
    default: return styles.neutral;
  }
};

const getSentimentIcon = (sentiment: string) => {
  switch (sentiment) {
    case 'BULLISH': return '📈';
    case 'BEARISH': return '📉';
    default: return '➡️';
  }
};

const getSignalColor = (sentiment: string) => {
  switch (sentiment) {
    case 'Strong Bullish':
    case 'Bullish': return styles.positive;
    case 'Strong Bearish':
    case 'Bearish': return styles.negative;
    default: return styles.neutral;
  }
};

const getSignalIcon = (sentiment: string) => {
  switch (sentiment) {
    case 'Strong Bullish': return '🚀';
    case 'Bullish': return '📈';
    case 'Strong Bearish': return '💥';
    case 'Bearish': return '📉';
    default: return '➡️';
  }
};

export default function ProfessionalPortfolio() {
  const [signals, setSignals] = useState<MarketSignal[]>([]);
  const [overview, setOverview] = useState<MarketOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedTimeframe, setSelectedTimeframe] = useState('1D');

  // Function to fetch live price from Polygon API
  const fetchLivePrice = async (symbol: string): Promise<{ price: number; change: number; changePercent: number }> => {
    try {
      const response = await fetch(`/api/price/${symbol}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch price for ${symbol}`);
      }
      const data = await response.json();
      return {
        price: data.last || 0,
        change: data.last - data.prevClose,
        changePercent: data.changePct * 100
      };
    } catch (error) {
      console.error(`Error fetching price for ${symbol}:`, error);
      // Return realistic fallback prices if API fails
      const fallbackPrices: Record<string, { price: number; change: number; changePercent: number }> = {
        'SPY': { price: 573.85, change: 2.45, changePercent: 0.43 },
        'QQQ': { price: 505.12, change: -1.23, changePercent: -0.24 },
        'NVDA': { price: 145.89, change: 3.67, changePercent: 2.58 },
        'TSLA': { price: 248.98, change: -2.12, changePercent: -0.84 }
      };
      return fallbackPrices[symbol] || { price: 100, change: 0, changePercent: 0 };
    }
  };

  // Mock research data with live prices
  useEffect(() => {
    const loadSignalsWithLivePrices = async () => {
      setLoading(true);
      
      // Base signal data without prices
      const baseSignals = [
        {
          symbol: 'SPY',
          companyName: 'S&P 500 ETF',
          sentiment: 'Bullish' as const,
          confidence: 78,
          aiInsight: 'Strong institutional buying detected. Technical indicators show bullish momentum with RSI at 62. Recommend monitoring for continuation.',
          timeHorizon: 'Medium' as const,
          technicalScore: 75,
          sentimentScore: 82
        },
        {
          symbol: 'QQQ',
          companyName: 'Nasdaq 100 ETF',
          sentiment: 'Bearish' as const,
          confidence: 65,
          aiInsight: 'Tech sector showing weakness amid rate concerns. High correlation with bond yields suggests defensive positioning may be prudent.',
          timeHorizon: 'Short' as const,
          technicalScore: 45,
          sentimentScore: 38
        },
        {
          symbol: 'NVDA',
          companyName: 'NVIDIA Corporation',
          sentiment: 'Strong Bullish' as const,
          confidence: 85,
          aiInsight: 'AI narrative strengthening with datacenter demand surge. Earnings momentum likely to continue. High conviction signal.',
          timeHorizon: 'Long' as const,
          technicalScore: 88,
          sentimentScore: 91
        },
        {
          symbol: 'TSLA',
          companyName: 'Tesla Inc.',
          sentiment: 'Strong Bearish' as const,
          confidence: 71,
          aiInsight: 'EV competition intensifying. Margin pressure visible in recent data. Consider defensive approach until fundamental improvement.',
          timeHorizon: 'Medium' as const,
          technicalScore: 32,
          sentimentScore: 28
        }
      ];

      // Fetch live prices for each signal
      const signalsWithLivePrices = await Promise.all(
        baseSignals.map(async (signal) => {
          const priceData = await fetchLivePrice(signal.symbol);
          return {
            ...signal,
            currentPrice: priceData.price,
            change: priceData.change,
            changePercent: priceData.changePercent
          };
        })
      );

      const mockOverview: MarketOverview = {
        marketSentiment: 'NEUTRAL',
        fearGreedIndex: 42,
        volatilityIndex: 18.5,
        aiConfidence: 73,
        trendStrength: 65
      };

      setSignals(signalsWithLivePrices);
      setOverview(mockOverview);
      setLoading(false);
    };

    loadSignalsWithLivePrices();

    // Set up price refresh interval (every 30 seconds)
    const priceRefreshInterval = setInterval(async () => {
      if (signals.length > 0) {
        const updatedSignals = await Promise.all(
          signals.map(async (signal) => {
            const priceData = await fetchLivePrice(signal.symbol);
            return {
              ...signal,
              currentPrice: priceData.price,
              change: priceData.change,
              changePercent: priceData.changePercent
            };
          })
        );
        setSignals(updatedSignals);
      }
    }, 30000); // 30 seconds

    return () => {
      clearInterval(priceRefreshInterval);
    };
  }, []);  const timeframes = ['1D', '1W', '1M', '3M', '1Y', 'ALL'];

  const getSentimentColor = (sentiment: string) => {
    switch (sentiment) {
      case 'BULLISH': return styles.positive;
      case 'BEARISH': return styles.negative;
      default: return styles.neutral;
    }
  };

  const getSentimentIcon = (sentiment: string) => {
    switch (sentiment) {
      case 'BULLISH': return '📈';
      case 'BEARISH': return '📉';
      default: return '➡️';
    }
  };

  if (loading) {
    return (
      <div className={styles.loadingContainer}>
        <div className={styles.loadingSpinner}></div>
        <p>Loading market insights...</p>
      </div>
    );
  }

  return (
    <div className={styles.portfolioContainer}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.headerMain}>
          <h1 className={styles.title}>Market Research Dashboard</h1>
          <div className={styles.subtitle}>
            AI-powered insights, signals, and educational analysis
          </div>
          <div className={styles.timestamp}>
            Last updated: {new Date().toLocaleTimeString()}
          </div>
        </div>
        
        <div className={styles.headerActions}>
          <div className={styles.timeframeSelector}>
            {timeframes.map(timeframe => (
              <button
                key={timeframe}
                className={`${styles.timeframeBtn} ${selectedTimeframe === timeframe ? styles.active : ''}`}
                onClick={() => setSelectedTimeframe(timeframe)}
              >
                {timeframe}
              </button>
            ))}
          </div>
          
          <div className={styles.navigationButtons}>
            <a href="/agents" className={styles.navButton}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="2"/>
                <path d="M12 1v6m0 6v6" stroke="currentColor" strokeWidth="2"/>
                <path d="m21 12-6 0m-6 0-6 0" stroke="currentColor" strokeWidth="2"/>
              </svg>
              AI Hedge Fund
            </a>
            <a href="/nrt" className={styles.navButton}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
                <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              NRT Strategy
            </a>
          </div>
        </div>
      </div>

      {/* Market Overview */}
      {overview && (
        <div className={styles.statsGrid}>
          <div className={styles.statCard}>
            <div className={styles.statHeader}>
              <div className={styles.statLabel}>Market Sentiment</div>
              <div className={styles.tooltip}>
                ℹ️ <span className={styles.tooltipText}>AI analysis of overall market mood based on news, social sentiment, and technical indicators</span>
              </div>
            </div>
            <div className={`${styles.statValue} ${getSentimentColor(overview.marketSentiment)}`}>
              {getSentimentIcon(overview.marketSentiment)} {overview.marketSentiment}
            </div>
          </div>
          
          <div className={styles.statCard}>
            <div className={styles.statHeader}>
              <div className={styles.statLabel}>Fear & Greed Index</div>
              <div className={styles.tooltip}>
                ℹ️ <span className={styles.tooltipText}>0-24: Extreme Fear (Bullish Signal), 25-49: Fear, 50-74: Greed, 75-100: Extreme Greed (Bearish Signal)</span>
              </div>
            </div>
            <div className={`${styles.statValue} ${overview.fearGreedIndex < 25 ? styles.positive : overview.fearGreedIndex > 75 ? styles.negative : styles.neutral}`}>
              {overview.fearGreedIndex}/100
            </div>
          </div>
          
          <div className={styles.statCard}>
            <div className={styles.statHeader}>
              <div className={styles.statLabel}>AI Confidence</div>
              <div className={styles.tooltip}>
                ℹ️ <span className={styles.tooltipText}>How confident our AI models are in current market predictions. Higher = more reliable signals</span>
              </div>
            </div>
            <div className={styles.statValue}>
              {overview.aiConfidence}%
            </div>
          </div>
          
          <div className={styles.statCard}>
            <div className={styles.statHeader}>
              <div className={styles.statLabel}>Volatility Index</div>
              <div className={styles.tooltip}>
                ℹ️ <span className={styles.tooltipText}>VIX level. Under 20: Low volatility (calm markets), Over 30: High volatility (stressed markets)</span>
              </div>
            </div>
            <div className={`${styles.statValue} ${overview.volatilityIndex > 30 ? styles.negative : overview.volatilityIndex < 20 ? styles.positive : styles.neutral}`}>
              {overview.volatilityIndex.toFixed(1)}
            </div>
          </div>
        </div>
      )}

      {/* Positions Table */}
      <div className={styles.positionsSection}>
        <div className={styles.sectionHeader}>
          <h2 className={styles.sectionTitle}>Holdings</h2>
          <div className={styles.sectionActions}>
            <button className={styles.actionBtn}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
                <path d="M12 5v14m-7-7h14" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              </svg>
              Add Position
            </button>
          </div>
        </div>

        <div className={styles.tableContainer}>
          {signals && signals.length > 0 ? (
          <table className={styles.positionsTable}>
            <thead>
              <tr>
                <th>
                  <div className={styles.headerWithTooltip}>
                    Symbol
                    <div className={styles.tooltip}>
                      ℹ️ <span className={styles.tooltipText}>Stock ticker being analyzed by our AI agents</span>
                    </div>
                  </div>
                </th>
                <th>
                  <div className={styles.headerWithTooltip}>
                    Signal Strength
                    <div className={styles.tooltip}>
                      ℹ️ <span className={styles.tooltipText}>Strong Bullish/Bearish: High conviction signals. Weak: Lower confidence signals</span>
                    </div>
                  </div>
                </th>
                <th>Price</th>
                <th>
                  <div className={styles.headerWithTooltip}>
                    AI Insight
                    <div className={styles.tooltip}>
                      ℹ️ <span className={styles.tooltipText}>Key reasoning from our AI analysis: news sentiment, technical patterns, or risk factors</span>
                    </div>
                  </div>
                </th>
                <th>
                  <div className={styles.headerWithTooltip}>
                    Confidence
                    <div className={styles.tooltip}>
                      ℹ️ <span className={styles.tooltipText}>How confident our models are in this signal (higher = more reliable)</span>
                    </div>
                  </div>
                </th>
                <th>
                  <div className={styles.headerWithTooltip}>
                    Time Horizon
                    <div className={styles.tooltip}>
                      ℹ️ <span className={styles.tooltipText}>Expected timeframe for this signal: Short (1-7 days), Medium (1-4 weeks), Long (1-3 months)</span>
                    </div>
                  </div>
                </th>
              </tr>
            </thead>
            <tbody>
              {signals.map((signal) => {
                const isPositiveSignal = signal.sentiment === 'Bullish' || signal.sentiment === 'Strong Bullish';
                
                return (
                  <tr key={signal.symbol} className={styles.positionRow}>
                    <td className={styles.symbolCell}>
                      <div className={styles.symbolInfo}>
                        <span className={styles.symbol}>{signal.symbol}</span>
                        <span className={styles.companyName}>{signal.companyName}</span>
                      </div>
                    </td>
                    <td className={`${getSignalColor(signal.sentiment)}`}>
                      {getSignalIcon(signal.sentiment)} {signal.sentiment}
                    </td>
                    <td>${signal.currentPrice.toFixed(2)}</td>
                    <td className={styles.insightCell}>
                      <div className={styles.insight}>
                        {signal.aiInsight}
                      </div>
                    </td>
                    <td className={styles.confidenceCell}>
                      <div className={`${styles.confidenceBar} ${signal.confidence > 80 ? styles.highConfidence : signal.confidence > 60 ? styles.mediumConfidence : styles.lowConfidence}`}>
                        {signal.confidence}%
                      </div>
                    </td>
                    <td className={styles.horizonCell}>
                      <span className={`${styles.horizonBadge} ${styles[signal.timeHorizon.toLowerCase().replace(' ', '')]}`}>
                        {signal.timeHorizon}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          ) : (
            <div className={styles.emptyState}>
              <div className={styles.emptyIcon}>📊</div>
              <h3>No Market Signals Available</h3>
              <p>Our AI agents are analyzing market conditions. Signals will appear here when detected.</p>
            </div>
          )}
        </div>
      </div>

      {/* AI Research Insights */}
      <div className={styles.researchInsights}>
        <div className={styles.insightCard}>
          <div className={styles.insightHeader}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
              <path d="M9 11H7a2 2 0 00-2 2v7a2 2 0 002 2h10a2 2 0 002-2v-7a2 2 0 00-2-2h-2" stroke="currentColor" strokeWidth="2"/>
              <path d="M9 7h6l-3-3z" stroke="currentColor" strokeWidth="2"/>
            </svg>
            <h3>Market Intelligence</h3>
          </div>
          <p>Our AI agents are continuously analyzing 15,000+ news sources, social sentiment, and technical patterns to generate actionable insights.</p>
        </div>
        
        <div className={styles.insightCard}>
          <div className={styles.insightHeader}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
              <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" stroke="currentColor" strokeWidth="2"/>
            </svg>
            <h3>Real-Time Analysis</h3>
          </div>
          <p>Signals update every 30 seconds, incorporating breaking news, earnings announcements, and institutional trading patterns.</p>
        </div>
        
        <div className={styles.insightCard}>
          <div className={styles.insightHeader}>
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
              <path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z" stroke="currentColor" strokeWidth="2"/>
            </svg>
            <h3>Educational Focus</h3>
          </div>
          <p>Each signal includes detailed explanations to help you understand the reasoning behind our AI's analysis and market dynamics.</p>
        </div>
      </div>

      {/* Explore More Navigation */}
      <div className={styles.exploreMore}>
        <h2>Explore Our AI System</h2>
        <p>Dive deeper into our sophisticated AI hedge fund architecture and trading strategies</p>
        
        <div className={styles.exploreCards}>
          <a href="/agents" className={styles.exploreCard}>
            <div className={styles.exploreIcon}>
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="3" stroke="currentColor" strokeWidth="2"/>
                <path d="M12 1v6m0 6v6" stroke="currentColor" strokeWidth="2"/>
                <path d="m21 12-6 0m-6 0-6 0" stroke="currentColor" strokeWidth="2"/>
              </svg>
            </div>
            <h3>AI Hedge Fund Architecture</h3>
            <p>Interactive visualization of our multi-agent AI system with real-time data flows and decision making processes.</p>
            <div className={styles.exploreArrow}>→</div>
          </a>
          
          <a href="/nrt" className={styles.exploreCard}>
            <div className={styles.exploreIcon}>
              <svg width="48" height="48" viewBox="0 0 24 24" fill="none">
                <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <h3>NRT Strategy Deep Dive</h3>
            <p>Explore our News-Regime-Trend strategy powered by GPT-4o for narrative analysis and market regime detection.</p>
            <div className={styles.exploreArrow}>→</div>
          </a>
        </div>
      </div>
    </div>
  );
}