'use client';

import { useEffect, useState, useRef } from 'react';
import styles from '../styles/NRTAgent.module.css';

interface RegimeData {
  name: string;
  probability: number;
  confidence: number;
  color: string;
  description: string;
}

interface FactorTilt {
  factor: string;
  name: string;
  tilt: number;
  weight: number;
  color: string;
}

interface NRTData {
  dominant_regime: string;
  regime_confidence: number;
  regime_probabilities: Record<string, number>;
  factor_tilts: Record<string, number>;
  target_weights: Record<string, number>;
  decision: string;
  confidence: number;
}

const REGIME_CONFIG = {
  growth_on: {
    name: 'Growth-On',
    color: '#00ff88',
    description: 'Risk-on environment with positive equity momentum and low volatility'
  },
  tightening: {
    name: 'Tightening',
    color: '#ffc400', 
    description: 'Policy tightening cycle with rising rates and defensive positioning'
  },
  inflation_shock: {
    name: 'Inflation Shock',
    color: '#ff6b35',
    description: 'Inflationary pressures driving commodity strength and duration weakness'
  },
  liquidity_crunch: {
    name: 'Liquidity Crunch',
    color: '#ff4444',
    description: 'Market stress with flight-to-quality and risk-off sentiment'
  }
};

const FACTOR_CONFIG = {
  MTUM: { name: 'Momentum', color: '#00ffff' },
  VLUE: { name: 'Value', color: '#ff00ff' },
  QUAL: { name: 'Quality', color: '#ffff00' },
  USMV: { name: 'Low Vol', color: '#00ff88' },
  TLT: { name: 'Long Duration', color: '#ffc400' },
  IEF: { name: 'Med Duration', color: '#ff9500' },
  SPY: { name: 'Equity Beta', color: '#8a2be2' }
};

export function NRTAgent() {
  const [nrtData, setNrtData] = useState<NRTData | null>(null);
  const [loading, setLoading] = useState(true);
  const [animationPhase, setAnimationPhase] = useState(0);
  const intervalRef = useRef<NodeJS.Timeout>();

  // Simulate NRT data (replace with real API call)
  const fetchNRTData = async (): Promise<NRTData> => {
    // Simulate API delay
    await new Promise(resolve => setTimeout(resolve, 500));
    
    return {
      dominant_regime: 'growth_on',
      regime_confidence: 0.73,
      regime_probabilities: {
        growth_on: 0.6,
        tightening: 0.2,
        inflation_shock: 0.1,
        liquidity_crunch: 0.1
      },
      factor_tilts: {
        MTUM: 0.4,
        VLUE: -0.1,
        QUAL: -0.1,
        USMV: 0.0,
        TLT: -0.3,
        IEF: -0.2,
        SPY: 0.3
      },
      target_weights: {
        MTUM: 0.18,
        VLUE: -0.05,
        QUAL: -0.05,
        USMV: 0.0,
        TLT: -0.15,
        IEF: -0.10,
        SPY: 0.15
      },
      decision: 'BUY',
      confidence: 0.82
    };
  };

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      try {
        const data = await fetchNRTData();
        setNrtData(data);
      } catch (error) {
        console.error('Failed to load NRT data:', error);
      } finally {
        setLoading(false);
      }
    };

    loadData();
    intervalRef.current = setInterval(loadData, 30000); // Update every 30s

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  // Animation cycle for visual effects
  useEffect(() => {
    const animationCycle = setInterval(() => {
      setAnimationPhase(prev => (prev + 1) % 4);
    }, 2000);

    return () => clearInterval(animationCycle);
  }, []);

  if (loading || !nrtData) {
    return (
      <div className={styles.nrtContainer}>
        <div className={styles.loadingSpinner}>
          <div className={styles.spinner}></div>
          <span>Analyzing Regime Probabilities...</span>
        </div>
      </div>
    );
  }

  const regimeData: RegimeData[] = Object.entries(nrtData.regime_probabilities).map(([key, prob]) => ({
    name: REGIME_CONFIG[key as keyof typeof REGIME_CONFIG]?.name || key,
    probability: prob,
    confidence: key === nrtData.dominant_regime ? nrtData.regime_confidence : prob,
    color: REGIME_CONFIG[key as keyof typeof REGIME_CONFIG]?.color || '#666',
    description: REGIME_CONFIG[key as keyof typeof REGIME_CONFIG]?.description || ''
  }));

  const factorTilts: FactorTilt[] = Object.entries(nrtData.factor_tilts).map(([key, tilt]) => ({
    factor: key,
    name: FACTOR_CONFIG[key as keyof typeof FACTOR_CONFIG]?.name || key,
    tilt,
    weight: nrtData.target_weights[key] || 0,
    color: FACTOR_CONFIG[key as keyof typeof FACTOR_CONFIG]?.color || '#666'
  }));

  const dominantRegime = regimeData.find(r => r.name === REGIME_CONFIG[nrtData.dominant_regime as keyof typeof REGIME_CONFIG]?.name);

  return (
    <div className={styles.nrtContainer}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.titleSection}>
          <h2>Narrative Regime Tilt (NRT)</h2>
          <p>Multi-regime factor allocation engine</p>
        </div>
        
        <div className={styles.statusBadge} style={{ borderColor: dominantRegime?.color }}>
          <span className={styles.statusDot} style={{ backgroundColor: dominantRegime?.color }}></span>
          <span>{dominantRegime?.name}</span>
          <span className={styles.confidence}>{(nrtData.regime_confidence * 100).toFixed(0)}%</span>
        </div>
      </div>

      <div className={styles.mainGrid}>
        {/* Regime Probabilities */}
        <div className={styles.regimePanel}>
          <h3>Market Regime Detection</h3>
          <p className={styles.regimeDescription}>
            {dominantRegime?.description}
          </p>
          
          <div className={styles.regimeChart}>
            {regimeData.map((regime, index) => (
              <div
                key={regime.name}
                className={`${styles.regimeBar} ${regime.name === dominantRegime?.name ? styles.dominant : ''}`}
                style={{
                  '--regime-color': regime.color,
                  '--regime-width': `${regime.probability * 100}%`,
                  '--animation-delay': `${index * 0.1}s`
                } as any}
              >
                <div className={styles.regimeBarFill} />
                <div className={styles.regimeLabel}>
                  <span className={styles.regimeName}>{regime.name}</span>
                  <span className={styles.regimeProb}>{(regime.probability * 100).toFixed(1)}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Factor Tilts Heatmap */}
        <div className={styles.factorPanel}>
          <h3>Factor Allocation Matrix</h3>
          
          <div className={styles.factorGrid}>
            {factorTilts.map(factor => (
              <div
                key={factor.factor}
                className={`${styles.factorCard} ${factor.tilt > 0 ? styles.positive : factor.tilt < 0 ? styles.negative : styles.neutral}`}
                style={{
                  '--factor-color': factor.color,
                  '--tilt-intensity': Math.abs(factor.tilt)
                } as any}
              >
                <div className={styles.factorHeader}>
                  <span className={styles.factorName}>{factor.name}</span>
                  <span className={styles.factorSymbol}>{factor.factor}</span>
                </div>
                
                <div className={styles.factorMetrics}>
                  <div className={styles.tiltBar}>
                    <div className={styles.tiltFill} style={{ width: `${Math.abs(factor.tilt) * 100}%` }} />
                    <span className={styles.tiltValue}>
                      {factor.tilt > 0 ? '+' : ''}{factor.tilt.toFixed(2)}
                    </span>
                  </div>
                  
                  <div className={styles.weightDisplay}>
                    <span>Weight: {(factor.weight * 100).toFixed(1)}%</span>
                  </div>
                </div>

                {/* Animated pulse for significant tilts */}
                {Math.abs(factor.tilt) > 0.2 && (
                  <div className={styles.factorPulse} />
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Decision Output */}
        <div className={styles.decisionPanel}>
          <h3>Portfolio Decision</h3>
          
          <div className={styles.decisionDisplay}>
            <div className={`${styles.decisionBadge} ${styles[nrtData.decision.toLowerCase()]}`}>
              <div className={styles.decisionIcon}>
                {nrtData.decision === 'BUY' && '📈'}
                {nrtData.decision === 'SELL' && '📉'}
                {nrtData.decision === 'HOLD' && '⏸️'}
              </div>
              <span className={styles.decisionText}>{nrtData.decision}</span>
            </div>
            
            <div className={styles.confidenceRing}>
              <svg viewBox="0 0 100 100" className={styles.confidenceSvg}>
                <circle
                  cx="50"
                  cy="50"
                  r="45"
                  fill="none"
                  stroke="rgba(255,255,255,0.1)"
                  strokeWidth="8"
                />
                <circle
                  cx="50"
                  cy="50"
                  r="45"
                  fill="none"
                  stroke={dominantRegime?.color}
                  strokeWidth="8"
                  strokeLinecap="round"
                  strokeDasharray={`${2 * Math.PI * 45}`}
                  strokeDashoffset={`${2 * Math.PI * 45 * (1 - nrtData.confidence)}`}
                  transform="rotate(-90 50 50)"
                />
              </svg>
              <div className={styles.confidenceText}>
                <span className={styles.confidenceValue}>{(nrtData.confidence * 100).toFixed(0)}%</span>
                <span className={styles.confidenceLabel}>Confidence</span>
              </div>
            </div>
          </div>

          <div className={styles.riskMetrics}>
            <div className={styles.metric}>
              <span>Gross Exposure</span>
              <span>{(factorTilts.reduce((sum, f) => sum + Math.abs(f.weight), 0) * 100).toFixed(1)}%</span>
            </div>
            <div className={styles.metric}>
              <span>Net Exposure</span>
              <span>{(factorTilts.reduce((sum, f) => sum + f.weight, 0) * 100).toFixed(1)}%</span>
            </div>
            <div className={styles.metric}>
              <span>Active Factors</span>
              <span>{factorTilts.filter(f => Math.abs(f.tilt) > 0.05).length}</span>
            </div>
          </div>
        </div>
      </div>

      {/* Data Flow Animation */}
      <div className={styles.dataFlow}>
        <div className={`${styles.flowParticle} ${styles[`phase${animationPhase}`]}`} />
        <div className={`${styles.flowParticle} ${styles[`phase${(animationPhase + 1) % 4}`]}`} />
        <div className={`${styles.flowParticle} ${styles[`phase${(animationPhase + 2) % 4}`]}`} />
      </div>
    </div>
  );
}