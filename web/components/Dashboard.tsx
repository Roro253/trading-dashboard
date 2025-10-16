'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { CSSProperties } from 'react';
import { fetchLatestEnsemble, fetchOptionsSummary, fetchPcr, fetchPrice } from '../lib/api';
import type { EnsembleResponse, OptionsSummary, PcrResponse, PriceResponse } from '../lib/types';
import { Panel } from './Panel';
import { AlertDraftPanel } from './AlertDraftPanel';
import { AuditTrail } from './AuditTrail';
import { HistoryTable } from './HistoryTable';
import { PerformancePanel } from './PerformancePanel';
import { PricePill } from './PricePill';
import { OptionsCard } from './OptionsCard';
import { SentimentChip } from './SentimentChip';
import styles from '../styles/Dashboard.module.css';

const DEFAULT_SYMBOL = 'QQQ';
const FEATURED_SYMBOLS = ['QQQ', 'SPY', 'IWM', 'ARKK', 'NVDA', 'TSLA'];
const ACADEMY_CARDS = [
  {
    title: 'Volatility Arcade',
    copy: 'Simulate IV crush vs expansion scenarios and learn how Delta and Vega respond.',
    action: 'Launch simulator',
  },
  {
    title: 'Liquidity Lab',
    copy: 'Interactive drill on order book depth and slippage during macro events.',
    action: 'Run lab',
  },
  {
    title: 'Agent Playbook',
    copy: 'Step inside the Technical agent to explore factor weightings and evidence stacks.',
    action: 'Explore agent',
  },
];

type InsightMode = 'insights' | 'playbook' | 'academy';

export function Dashboard() {
  const [selectedSymbol, setSelectedSymbol] = useState<string>(DEFAULT_SYMBOL);
  const [latest, setLatest] = useState<EnsembleResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [insightMode, setInsightMode] = useState<InsightMode>('insights');

  const [price, setPrice] = useState<PriceResponse | null>(null);
  const [priceLoading, setPriceLoading] = useState(false);
  const [priceError, setPriceError] = useState<string | null>(null);

  const [optionsSummary, setOptionsSummary] = useState<OptionsSummary | null>(null);
  const [optionsLoading, setOptionsLoading] = useState(false);
  const [optionsError, setOptionsError] = useState<string | null>(null);

  const [pcr, setPcr] = useState<PcrResponse | null>(null);
  const [pcrLoading, setPcrLoading] = useState(false);
  const [pcrError, setPcrError] = useState<string | null>(null);

  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const loadPrice = useCallback(async () => {
    setPriceLoading(true);
    try {
      const data = await fetchPrice(selectedSymbol);
      if (!mountedRef.current) {
        return;
      }
      setPrice(data);
      setPriceError(null);
    } catch (err) {
      if (!mountedRef.current) {
        return;
      }
      setPriceError('Price feed temporarily unavailable');
    } finally {
      if (mountedRef.current) {
        setPriceLoading(false);
      }
    }
  }, [selectedSymbol]);

  const loadOptions = useCallback(async () => {
    setOptionsLoading(true);
    try {
      const summary = await fetchOptionsSummary(selectedSymbol);
      if (!mountedRef.current) {
        return;
      }
      setOptionsSummary(summary);
      setOptionsError(null);
    } catch (err) {
      if (!mountedRef.current) {
        return;
      }
      setOptionsError('Options feed paused');
    } finally {
      if (mountedRef.current) {
        setOptionsLoading(false);
      }
    }
  }, [selectedSymbol]);

  const loadPcr = useCallback(async () => {
    setPcrLoading(true);
    try {
      const data = await fetchPcr();
      if (!mountedRef.current) {
        return;
      }
      setPcr(data);
      setPcrError(null);
    } catch (err) {
      if (!mountedRef.current) {
        return;
      }
      setPcrError('PCR feed unavailable');
    } finally {
      if (mountedRef.current) {
        setPcrLoading(false);
      }
    }
  }, []);

  useEffect(() => {
    setPrice(null);
    setPriceError(null);
    void loadPrice();
    const interval = window.setInterval(() => {
      void loadPrice();
    }, 15_000);
    return () => {
      window.clearInterval(interval);
    };
  }, [loadPrice]);

  useEffect(() => {
    void loadOptions();
    const interval = window.setInterval(() => {
      void loadOptions();
    }, 60_000);
    return () => {
      window.clearInterval(interval);
    };
  }, [loadOptions]);

  useEffect(() => {
    void loadPcr();
    const interval = window.setInterval(() => {
      void loadPcr();
    }, 5 * 60_000);
    return () => {
      window.clearInterval(interval);
    };
  }, [loadPcr]);

  useEffect(() => {
    let mounted = true;

    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchLatestEnsemble(selectedSymbol);
        if (!mounted) {
          return;
        }
        setLatest(data);
      } catch (err) {
        if (!mounted) {
          return;
        }
        const status = (err as Error & { status?: number })?.status;
        if (status === 404) {
          setLatest(null);
          setError(null);
        } else {
          setError(err instanceof Error ? err.message : 'Failed to load latest alert');
        }
      } finally {
        if (mounted) {
          setLoading(false);
        }
      }
    };

    void load();
    const interval = setInterval(load, 60_000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, [selectedSymbol]);

  const confidencePct = useMemo(() => Math.round((latest?.confidence ?? 0) * 100), [latest]);

  const ringStyles = useMemo(
    () =>
      ({
        '--confidence': confidencePct,
      }) as CSSProperties,
    [confidencePct],
  );

  const portfolioSnapshot = (latest?.portfolio_snapshot as Record<string, unknown>) ?? null;
  const auditorChecks =
    ((portfolioSnapshot?.auditor_notes as { checks?: { name: string; status: string; detail: string }[] })?.checks ??
      []) as { name: string; status: string; detail: string }[];
  const riskDetails = (portfolioSnapshot?.risk as { reasons?: string[] } | undefined)?.reasons ?? [];

  const agentHighlights = useMemo(() => {
    const snapshot = (portfolioSnapshot?.agents as Record<string, unknown>) ?? {};
    return Object.entries(snapshot)
      .map(([agentKey, raw]) => {
        const data = (raw ?? {}) as Record<string, unknown>;
        const decision = typeof data.decision === 'string' ? (data.decision as string) : '—';
        const confidence = Number(data.confidence ?? 0);
        const narrative = (data.notes as string | undefined) ?? (data.summary as string | undefined) ?? '';
        return {
          agent: agentKey,
          decision,
          confidence,
          narrative,
        };
      })
      .sort((a, b) => b.confidence - a.confidence)
      .slice(0, 3);
  }, [portfolioSnapshot]);

  const tapeItems = useMemo(() => {
    const items: { label: string; value: string; tone: 'up' | 'down' | 'steady' }[] = [];

    if (price) {
      const pct = price.changePct * 100;
      const tone = pct > 0 ? 'up' : pct < 0 ? 'down' : 'steady';
      items.push({
        label: `${selectedSymbol} Last`,
        value: Number.isFinite(price.last) ? `$${price.last.toFixed(2)}` : '—',
        tone,
      });
      items.push({
        label: 'Δ%',
        value: Number.isFinite(pct) ? `${pct >= 0 ? '+' : ''}${pct.toFixed(2)}%` : '—',
        tone,
      });
    } else {
      items.push({ label: `${selectedSymbol} Last`, value: 'loading…', tone: 'steady' });
      items.push({ label: 'Δ%', value: '—', tone: 'steady' });
    }

    const iv = optionsSummary?.iv30 ?? null;
    const ivChange = optionsSummary?.ivChangePctDoD ?? null;
    items.push({
      label: 'IV30',
      value: iv != null ? `${iv.toFixed(1)}%` : 'scanning…',
      tone: ivChange != null && ivChange <= -5 ? 'down' : ivChange != null && ivChange >= 5 ? 'up' : 'steady',
    });

    const skew = optionsSummary?.skew25d ?? null;
    items.push({
      label: 'Skew 25Δ',
      value: skew != null ? `${skew.toFixed(2)}` : 'neutral',
      tone: skew != null && Math.abs(skew) >= 3 ? (skew > 0 ? 'up' : 'down') : 'steady',
    });

    const pcrToday = Number.isFinite(pcr?.today ?? NaN) ? pcr!.today : null;
    items.push({
      label: 'PCR Equity',
      value: pcrToday != null ? pcrToday.toFixed(2) : '—',
      tone: pcr?.isExtremeHigh ? 'up' : pcr?.isExtremeLow ? 'down' : 'steady',
    });

    return items;
  }, [optionsSummary, pcr, price, selectedSymbol]);

  const renderInsightSection = () => {
    if (insightMode === 'playbook') {
      const ticket = (latest?.rth_ticket as Record<string, unknown>) ?? null;
      const entryRules = (ticket?.entry_rules as string[]) ?? [];
      const stopRules = (ticket?.stop_rules as string[]) ?? [];
      const targets = (ticket?.targets as string[]) ?? [];

      if (!ticket) {
        return <div className={styles.emptyState}>We&apos;ll surface a structured play when the agents align on the next opportunity.</div>;
      }

      return (
        <div className={styles.playbookGrid}>
          <div className={styles.playbookColumn}>
            <h4>Entry Script</h4>
            <ul>
              {entryRules.length > 0 ? entryRules.map((rule) => <li key={rule}>{rule}</li>) : <li>Watching price action...</li>}
            </ul>
          </div>
          <div className={styles.playbookColumn}>
            <h4>Risk Controls</h4>
            <ul>
              {stopRules.length > 0 ? stopRules.map((rule) => <li key={rule}>{rule}</li>) : <li>Stops will appear once risk gates unlock.</li>}
            </ul>
          </div>
          <div className={styles.playbookColumn}>
            <h4>Target Ladder</h4>
            <ul>
              {targets.length > 0 ? targets.map((target) => <li key={target}>{target}</li>) : <li>No defined targets until conviction increases.</li>}
            </ul>
          </div>
        </div>
      );
    }

    if (insightMode === 'academy') {
      return (
        <div className={styles.academyGrid}>
          {ACADEMY_CARDS.map((card) => (
            <article key={card.title} className={styles.academyCard}>
              <header>
                <h4>{card.title}</h4>
                <span className={styles.academyBadge}>Interactive</span>
              </header>
              <p>{card.copy}</p>
              <button type="button" className={styles.glassButton}>
                {card.action}
              </button>
            </article>
          ))}
        </div>
      );
    }

    return (
      <div className={styles.checkGrid}>
        {auditorChecks.length > 0 ? (
          auditorChecks.map((check) => (
            <article
              key={check.name}
              className={`${styles.checkCard} ${check.status === 'fail' ? styles.checkFail : styles.checkPass}`}
            >
              <header>
                <span>{check.name}</span>
                <span className={styles.checkBadge}>{check.status.toUpperCase()}</span>
              </header>
              <p>{check.detail}</p>
            </article>
          ))
        ) : (
          <article className={styles.checkCard}>
            <header>
              <span>Auditor</span>
              <span className={styles.checkBadge}>LIVE</span>
            </header>
            <p>The auditor will light up once we record a fresh run for {selectedSymbol}.</p>
          </article>
        )}
        <article className={styles.checkCard}>
          <header>
            <span>Risk Broadcast</span>
            <span className={styles.checkBadge}>{latest?.risk_pass ? 'CLEAR' : 'WATCH'}</span>
          </header>
          {riskDetails.length > 0 ? (
            <ul className={styles.checkList}>
              {riskDetails.map((reason) => (
                <li key={reason}>{reason.replaceAll('_', ' ')}</li>
              ))}
            </ul>
          ) : (
            <p>Risk desk has no active veto flags.</p>
          )}
        </article>
      </div>
    );
  };

  return (
    <div className={styles.dashboard}>
      {error && <div className={styles.banner}>{error}</div>}

      <section className={styles.hero}>
        <div className={styles.heroContent}>
          <div className={styles.heroLead}>
            <span className={styles.kicker}>Futuristic Hedge Command • 2025 Edition</span>
            <h1>Alpha Terminal for Modern Market Tacticians</h1>
            <p>
              Command multi-agent intelligence, risk gating, and options telemetry in one neon-lit cockpit. Tap into the
              flow, learn the playbook, and make the markets feel like a game you&apos;re built to win.
            </p>
            <div className={styles.symbolChooser}>
              {FEATURED_SYMBOLS.map((symbol) => (
                <button
                  key={symbol}
                  type="button"
                  className={`${styles.symbolButton} ${symbol === selectedSymbol ? styles.symbolActive : ''}`}
                  onClick={() => setSelectedSymbol(symbol)}
                  disabled={loading && symbol === selectedSymbol}
                >
                  <span>{symbol}</span>
                  {symbol === selectedSymbol && <span className={styles.symbolPulse} />}
                </button>
              ))}
            </div>
          </div>

          <div className={styles.heroStats}>
            <div className={styles.marketStack}>
              <PricePill
                symbol={selectedSymbol}
                price={price}
                loading={priceLoading}
                error={priceError}
                onRetry={loadPrice}
              />
              <SentimentChip data={pcr} loading={pcrLoading} error={pcrError} onRetry={loadPcr} />
            </div>
            <div className={styles.confidenceShell}>
              <div className={styles.confidenceRing} style={ringStyles}>
                <div className={styles.confidenceValue}>{confidencePct}%</div>
                <span className={styles.confidenceLabel}>Confidence</span>
              </div>
              <p>Weighted by orchestrator portfolio logic &amp; real-time volatility regime.</p>
            </div>
            <article
              className={`${styles.statusCard} ${
                latest?.risk_pass === false ? styles.statusWarning : styles.statusPositive
              }`}
            >
              <header>
                <span>Risk Gate</span>
                <strong>{latest?.risk_pass === false ? 'On Hold' : latest ? 'Greenlit' : 'Awaiting'}</strong>
              </header>
              <p>
                {latest?.risk_pass === false
                  ? `Primary blocker: ${(riskDetails[0] ?? 'awaiting fresh data').replaceAll('_', ' ')}`
                  : 'Liquidity, time, and event filters all aligned.'}
              </p>
            </article>
            <article className={styles.statusCard}>
              <header>
                <span>Top Agent</span>
                <strong>{agentHighlights[0]?.agent ?? '—'}</strong>
              </header>
              <p>
                {agentHighlights[0]
                  ? `${agentHighlights[0].decision} @ ${(agentHighlights[0].confidence * 100).toFixed(0)}% · ${
                      agentHighlights[0].narrative || 'Confidence pulse stabilising.'
                    }`
                  : 'Agent consensus warming up for the next play.'}
              </p>
            </article>
          </div>
        </div>

        <div className={styles.tickerTape}>
          <div className={styles.tickerInner}>
            {[0, 1].flatMap((loop) => tapeItems.map((item) => ({ ...item, key: `${item.label}-${loop}` }))).map((item) => (
              <span key={item.key} className={`${styles.tickerItem} ${styles[`ticker${item.tone}`]}`}>
                <strong>{item.label}</strong>
                <em>{item.value}</em>
              </span>
            ))}
          </div>
        </div>
      </section>

      <section className={styles.deck}>
        <div className={styles.insightDeck}>
          <article className={styles.insightCard}>
            <span className={styles.cardEyebrow}>Agent Alignment</span>
            <h3>{agentHighlights[0]?.decision ?? 'Signal forming'} on {selectedSymbol}</h3>
            <p>
              {agentHighlights[1]
                ? `${agentHighlights[1].agent} backs this move at ${(agentHighlights[1].confidence * 100).toFixed(0)}%.`
                : 'We\'ll highlight cross-agent consensus as soon as it syncs.'}
            </p>
            <footer>
              {agentHighlights.map((agent) => (
                <span key={agent.agent} className={styles.agentTag}>
                  {agent.agent}: {(agent.confidence * 100).toFixed(0)}%
                </span>
              ))}
            </footer>
          </article>

          <OptionsCard
            symbol={selectedSymbol}
            summary={optionsSummary}
            loading={optionsLoading}
            error={optionsError}
            onRetry={loadOptions}
          />

          <article className={styles.insightCard}>
            <span className={styles.cardEyebrow}>Learning Spark</span>
            <h3>Decode risk like a Wall Street pro</h3>
            <p>Walk through blackout windows, RTH gatekeeping, and capital allocation heuristics in our Academy.</p>
            <button type="button" className={styles.glassButton}>
              Enter the Academy
            </button>
          </article>
        </div>

        <div className={styles.modeSwitch}>
          <button
            type="button"
            className={`${styles.modeButton} ${insightMode === 'insights' ? styles.modeActive : ''}`}
            onClick={() => setInsightMode('insights')}
          >
            Insights
          </button>
          <button
            type="button"
            className={`${styles.modeButton} ${insightMode === 'playbook' ? styles.modeActive : ''}`}
            onClick={() => setInsightMode('playbook')}
          >
            Playbook
          </button>
          <button
            type="button"
            className={`${styles.modeButton} ${insightMode === 'academy' ? styles.modeActive : ''}`}
            onClick={() => setInsightMode('academy')}
          >
            Academy
          </button>
        </div>

        <div className={styles.modePanel}>{renderInsightSection()}</div>
      </section>

      <div className={styles.grid}>
        <div className={styles.sidebar}>
          <Panel title="Alert Draft" subtitle="RTH Options Playbook">
            <AlertDraftPanel latest={latest} loading={loading} />
          </Panel>
          <Panel title="Audit Trail" subtitle="Key checks & evidence">
            <AuditTrail latest={latest} loading={loading} />
          </Panel>
        </div>
        <div className={styles.mainContent}>
          <Panel title="Alert History" subtitle="Server-side pagination with CSV export">
            <HistoryTable />
          </Panel>
          <Panel title="Performance" subtitle="Rolling agent stats (7d/30d)">
            <PerformancePanel />
          </Panel>
        </div>
      </div>
    </div>
  );
}
