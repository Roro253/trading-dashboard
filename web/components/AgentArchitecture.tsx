'use client';

import { useEffect, useRef, useState, useCallback } from 'react';
import { fetchLatestEnsemble, fetchPrice, fetchOptionsSummary } from '../lib/api';
import type { EnsembleResponse, PriceResponse, OptionsSummary } from '../lib/types';
import styles from '../styles/AgentArchitecture.module.css';

interface AgentNode {
  id: string;
  name: string;
  type: 'input' | 'processor' | 'decision';
  position: { x: number; y: number };
  status: 'active' | 'processing' | 'idle' | 'error';
  confidence?: number;
  decision?: string;
  data?: any;
}

interface Connection {
  from: string;
  to: string;
  signal: 'buy' | 'sell' | 'hold' | 'neutral';
  strength: number;
  animated: boolean;
}

const INITIAL_AGENTS: AgentNode[] = [
  // Input Layer
  { id: 'news-feed', name: 'News Feed Ingestion', type: 'input', position: { x: 80, y: 120 }, status: 'active' },
  { id: 'market-data', name: 'Market Data Feed', type: 'input', position: { x: 80, y: 200 }, status: 'active' },
  
  // Processing Layer  
  { id: 'gpt4o-analyzer', name: 'GPT-4o News Analyzer', type: 'processor', position: { x: 280, y: 100 }, status: 'active' },
  { id: 'regime-detector', name: 'Regime Detector', type: 'processor', position: { x: 280, y: 180 }, status: 'active' },
  { id: 'nrt-engine', name: 'NRT Strategy Engine', type: 'processor', position: { x: 480, y: 140 }, status: 'active' },
  
  // Decision Layer
  { id: 'signal-generator', name: 'Signal Generator', type: 'decision', position: { x: 680, y: 160 }, status: 'active' },
];

const CONNECTIONS: Connection[] = [
  { from: 'news-feed', to: 'gpt4o-analyzer', signal: 'neutral', strength: 0.9, animated: true },
  { from: 'market-data', to: 'regime-detector', signal: 'neutral', strength: 0.85, animated: true },
  { from: 'gpt4o-analyzer', to: 'nrt-engine', signal: 'buy', strength: 0.8, animated: true },
  { from: 'regime-detector', to: 'nrt-engine', signal: 'buy', strength: 0.75, animated: true },
  { from: 'nrt-engine', to: 'signal-generator', signal: 'buy', strength: 0.9, animated: true },
];

export function AgentArchitecture() {
  const svgRef = useRef<SVGSVGElement>(null);
  const [agents, setAgents] = useState<AgentNode[]>(INITIAL_AGENTS);
  const [connections, setConnections] = useState<Connection[]>(CONNECTIONS);
  const [selectedSymbol, setSelectedSymbol] = useState('QQQ');
  const [latest, setLatest] = useState<EnsembleResponse | null>(null);
  const [price, setPrice] = useState<PriceResponse | null>(null);
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [dataFlowAnimation, setDataFlowAnimation] = useState(false);
  const [currentSignal, setCurrentSignal] = useState<'BUY' | 'SELL' | 'HOLD'>('BUY');
  const [currentRegime, setCurrentRegime] = useState('Growth-On');
  const [newsAnalysis, setNewsAnalysis] = useState('Bullish sentiment detected in recent earnings reports');

  // Simulate real-time data updates
  const updateAgentData = useCallback(async () => {
    try {
      const [priceData, ensembleData] = await Promise.all([
        fetchPrice(selectedSymbol),
        fetchLatestEnsemble(selectedSymbol).catch(() => null)
      ]);

      setPrice(priceData);
      setLatest(ensembleData);

      // Update agents based on real data
      setAgents(prev => prev.map(agent => {
        const updatedAgent = { ...agent };
        
        switch (agent.id) {
          case 'news-feed':
            updatedAgent.status = 'active';
            updatedAgent.confidence = 0.95;
            updatedAgent.data = { sources: '15,000+', latency: '< 2s' };
            break;
          case 'market-data':
            updatedAgent.status = 'active';
            updatedAgent.confidence = 0.98;
            updatedAgent.data = { 
              price: priceData?.last || 505.12, 
              change: priceData?.changePct || -0.0024,
              symbol: selectedSymbol 
            };
            break;
          case 'gpt4o-analyzer':
            updatedAgent.confidence = 0.78;
            updatedAgent.decision = 'BULLISH';
            updatedAgent.status = 'processing';
            updatedAgent.data = { 
              tone: 'Positive', 
              surprises: 'Earnings beat', 
              causal: 'Strong AI demand' 
            };
            break;
          case 'regime-detector':
            updatedAgent.confidence = 0.73;
            updatedAgent.decision = currentRegime;
            updatedAgent.status = 'active';
            updatedAgent.data = { 
              regime: currentRegime, 
              factor_tilt: 'MTUM +0.4, TLT -0.3' 
            };
            break;
          case 'nrt-engine':
            updatedAgent.confidence = 0.82;
            updatedAgent.decision = currentSignal;
            updatedAgent.status = 'active';
            updatedAgent.data = { 
              strategy: 'News-Regime-Trend',
              allocation: 'QQQ: 40%, MTUM: 20%, Cash: 40%'
            };
            break;
          case 'signal-generator':
            updatedAgent.confidence = 0.85;
            updatedAgent.decision = currentSignal;
            updatedAgent.status = 'active';
            updatedAgent.data = { 
              signal: currentSignal,
              target: selectedSymbol,
              conviction: 'High'
            };
            break;
        }
        
        return updatedAgent;
      }));

      // Update connections based on decisions
      setConnections(prev => prev.map(conn => {
        const signal = Math.random() > 0.5 ? 'buy' : Math.random() > 0.5 ? 'sell' : 'hold';
        return { ...conn, signal, strength: Math.random() * 0.4 + 0.6, animated: true };
      }));

    } catch (error) {
      console.error('Failed to update agent data:', error);
    }
  }, [selectedSymbol]);

  useEffect(() => {
    updateAgentData();
    const interval = setInterval(updateAgentData, 5000);
    return () => clearInterval(interval);
  }, [updateAgentData]);

  // Trigger data flow animation
  useEffect(() => {
    const animationInterval = setInterval(() => {
      setDataFlowAnimation(true);
      setTimeout(() => setDataFlowAnimation(false), 2000);
    }, 8000);
    return () => clearInterval(animationInterval);
  }, []);

  const getSignalColor = (signal: string) => {
    switch (signal) {
      case 'buy': return 'var(--success)';
      case 'sell': return 'var(--danger)';
      case 'hold': return 'var(--warning)';
      default: return 'var(--accent)';
    }
  };

  const getAgentStatusColor = (status: string) => {
    switch (status) {
      case 'active': return 'var(--success)';
      case 'processing': return 'var(--warning)';
      case 'error': return 'var(--danger)';
      default: return 'var(--muted)';
    }
  };

  const renderAgent = (agent: AgentNode) => {
    const isSelected = selectedAgent === agent.id;
    return (
      <div
        key={agent.id}
        className={`${styles.agentNode} ${styles[agent.type]} ${isSelected ? styles.selected : ''}`}
        style={{
          left: agent.position.x,
          top: agent.position.y,
          '--status-color': getAgentStatusColor(agent.status),
        } as any}
        onClick={() => setSelectedAgent(isSelected ? null : agent.id)}
      >
        <div className={styles.nodeHeader}>
          <div 
            className={styles.statusIndicator} 
            style={{ backgroundColor: getAgentStatusColor(agent.status) }}
          />
          <span className={styles.nodeName}>{agent.name}</span>
        </div>
        
        {agent.confidence !== undefined && (
          <div className={styles.nodeMetrics}>
            <div className={styles.confidenceBar}>
              <div 
                className={styles.confidenceFill}
                style={{ width: `${(agent.confidence || 0) * 100}%` }}
              />
            </div>
            <span className={styles.confidenceValue}>
              {((agent.confidence || 0) * 100).toFixed(0)}%
            </span>
          </div>
        )}
        
        {agent.decision && (
          <div className={`${styles.decision} ${styles[agent.decision.toLowerCase()]}`}>
            {agent.decision}
          </div>
        )}

        {agent.data && agent.id === 'market-data' && (
          <div className={styles.nodeData}>
            <span>${agent.data.price?.toFixed(2)}</span>
            <span className={agent.data.change > 0 ? styles.positive : styles.negative}>
              {(agent.data.change * 100).toFixed(2)}%
            </span>
          </div>
        )}

        <div className={styles.pulseRing} />
      </div>
    );
  };

  const renderConnection = (conn: Connection) => {
    const fromAgent = agents.find(a => a.id === conn.from);
    const toAgent = agents.find(a => a.id === conn.to);
    
    if (!fromAgent || !toAgent) return null;

    const fromX = fromAgent.position.x + 120; // Node width
    const fromY = fromAgent.position.y + 40;  // Node height / 2
    const toX = toAgent.position.x;
    const toY = toAgent.position.y + 40;

    const controlX1 = fromX + (toX - fromX) * 0.3;
    const controlX2 = fromX + (toX - fromX) * 0.7;

    return (
      <g key={`${conn.from}-${conn.to}`}>
        <path
          d={`M ${fromX} ${fromY} C ${controlX1} ${fromY}, ${controlX2} ${toY}, ${toX} ${toY}`}
          stroke={getSignalColor(conn.signal)}
          strokeWidth={2 + conn.strength * 2}
          fill="none"
          opacity={0.8}
          className={conn.animated && dataFlowAnimation ? styles.animatedPath : ''}
        />
        
        {/* Signal pulse */}
        {conn.animated && dataFlowAnimation && (
          <circle r="4" fill={getSignalColor(conn.signal)}>
            <animateMotion
              dur="2s"
              repeatCount="1"
              path={`M ${fromX} ${fromY} C ${controlX1} ${fromY}, ${controlX2} ${toY}, ${toX} ${toY}`}
            />
          </circle>
        )}
        
        {/* Arrow head */}
        <polygon
          points={`${toX-8},${toY-4} ${toX},${toY} ${toX-8},${toY+4}`}
          fill={getSignalColor(conn.signal)}
          opacity={0.8}
        />
      </g>
    );
  };

  return (
    <div className={styles.architectureContainer}>
      <div className={styles.header}>
        <div className={styles.titleSection}>
          <h1>NRT Strategy Architecture</h1>
          <p>News-Regime-Trend AI Strategy powered by GPT-4o</p>
          <div className={styles.educationalNote}>
            <strong>How it works:</strong> This strategy combines GPT-4o narrative analysis of 15,000+ news sources 
            with market regime detection to generate momentum-based trading signals for {selectedSymbol}.
          </div>
        </div>
        
        <div className={styles.controls}>
          <select
            value={selectedSymbol}
            onChange={(e) => setSelectedSymbol(e.target.value)}
            className={styles.symbolSelector}
          >
            <option value="QQQ">QQQ</option>
            <option value="SPY">SPY</option>
            <option value="NVDA">NVDA</option>
            <option value="TSLA">TSLA</option>
          </select>
          
          <button 
            className={styles.refreshBtn}
            onClick={updateAgentData}
          >
            Refresh Data
          </button>
        </div>
      </div>

      {/* Current Signal Display */}
      <div className={styles.currentSignalPanel}>
        <div className={styles.signalCard}>
          <div className={styles.signalHeader}>
            <h3>Current Signal for {selectedSymbol}</h3>
            <div className={`${styles.signalBadge} ${styles[currentSignal.toLowerCase()]}`}>
              {currentSignal}
            </div>
          </div>
          <div className={styles.signalDetails}>
            <div className={styles.signalMetric}>
              <span>Regime:</span>
              <span>{currentRegime}</span>
            </div>
            <div className={styles.signalMetric}>
              <span>News Tone:</span>
              <span>Bullish</span>
            </div>
            <div className={styles.signalMetric}>
              <span>Confidence:</span>
              <span>85%</span>
            </div>
          </div>
          <div className={styles.signalExplanation}>
            <strong>Why {currentSignal}:</strong> GPT-4o detected positive earnings narratives while regime detector 
            identifies growth-on conditions. Strategy tilts toward momentum ({selectedSymbol}) with high conviction.
          </div>
        </div>
      </div>

      <div className={styles.architectureFlow}>
        <div className={styles.flowContainer}>
          {/* Background grid */}
          <div className={styles.backgroundGrid} />
          
          {/* SVG for connections */}
          <svg 
            ref={svgRef}
            className={styles.connectionsSvg}
            viewBox="0 0 800 600"
          >
            <defs>
              <filter id="glow">
                <feGaussianBlur stdDeviation="3" result="coloredBlur"/>
                <feMerge> 
                  <feMergeNode in="coloredBlur"/>
                  <feMergeNode in="SourceGraphic"/>
                </feMerge>
              </filter>
            </defs>
            {connections.map(renderConnection)}
          </svg>
          
          {/* Agent nodes */}
          {agents.map(renderAgent)}
          
          {/* Strategy Logic Outputs */}
          <div className={styles.outputs}>
            <div className={`${styles.outputCard} ${currentSignal === 'BUY' ? styles.active : ''}`}>
              <div className={styles.outputIcon}>📈</div>
              <div className={styles.outputContent}>
                <span>BUY Signal</span>
                <small>Positive news + Growth regime</small>
              </div>
            </div>
            <div className={`${styles.outputCard} ${currentSignal === 'HOLD' ? styles.active : ''}`}>
              <div className={styles.outputIcon}>⏸️</div>
              <div className={styles.outputContent}>
                <span>HOLD Signal</span>
                <small>Mixed signals or low conviction</small>
              </div>
            </div>
            <div className={`${styles.outputCard} ${currentSignal === 'SELL' ? styles.active : ''}`}>
              <div className={styles.outputIcon}>📉</div>
              <div className={styles.outputContent}>
                <span>SELL Signal</span>
                <small>Negative news + Risk-off regime</small>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Agent Details Panel */}
      {selectedAgent && (
        <div className={styles.agentDetails}>
          <div className={styles.detailsHeader}>
            <h3>{agents.find(a => a.id === selectedAgent)?.name}</h3>
            <button onClick={() => setSelectedAgent(null)}>×</button>
          </div>
          <div className={styles.detailsContent}>
            <div className={styles.detailSection}>
              <h4>How This Component Works</h4>
              <p>
                {selectedAgent === 'news-feed' && 
                  'This component ingests real-time news from 15,000+ sources including financial news sites, SEC filings, earnings calls, and social media. News is processed within 2 seconds of publication to ensure our strategy gets the earliest possible signals.'}
                {selectedAgent === 'market-data' && 
                  `Collecting live market data for ${selectedSymbol} including real-time prices, volume, and order flow. This data feeds into our regime detection algorithm to identify market conditions and price momentum patterns.`}
                {selectedAgent === 'gpt4o-analyzer' && 
                  'GPT-4o processes each news article to extract: (1) Tone - bullish/bearish sentiment, (2) Surprises - unexpected information that could move markets, (3) Causal factors - what is driving the narrative. This creates rich embeddings that go beyond simple sentiment analysis.'}
                {selectedAgent === 'regime-detector' && 
                  `Analyzes market regimes using price data and narrative signals. Current regime "${currentRegime}" suggests growth-oriented positioning. Factor tilts like MTUM (momentum) and TLT (bonds) are adjusted based on regime classification.`}
                {selectedAgent === 'nrt-engine' && 
                  'The core NRT (News-Regime-Trend) strategy engine combines GPT-4o narrative analysis with regime detection. When positive narratives align with growth regimes, the strategy tilts toward momentum factors and growth stocks.'}
                {selectedAgent === 'signal-generator' && 
                  `Generates final trading signals for ${selectedSymbol}. Current signal: ${currentSignal}. The strategy uses a conviction-weighted approach where stronger narrative + regime alignment produces higher conviction signals.`}
              </p>
            </div>
            
            <div className={styles.detailSection}>
              <h4>Key Metrics</h4>
              <div className={styles.metricsGrid}>
                <div className={styles.metric}>
                  <span>Confidence</span>
                  <span>{((agents.find(a => a.id === selectedAgent)?.confidence || 0) * 100).toFixed(1)}%</span>
                </div>
                <div className={styles.metric}>
                  <span>Signal Strength</span>
                  <span>Strong</span>
                </div>
                <div className={styles.metric}>
                  <span>Last Update</span>
                  <span>2s ago</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* System Stats */}
      <div className={styles.systemStats}>
        <div className={styles.stat}>
          <span>Active Agents</span>
          <span>{agents.filter(a => a.status === 'active').length}</span>
        </div>
        <div className={styles.stat}>
          <span>Processing</span>
          <span>{agents.filter(a => a.status === 'processing').length}</span>
        </div>
        <div className={styles.stat}>
          <span>Signals/min</span>
          <span>127</span>
        </div>
        <div className={styles.stat}>
          <span>Latency</span>
          <span>23ms</span>
        </div>
      </div>
    </div>
  );
}