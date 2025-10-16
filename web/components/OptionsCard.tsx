'use client';

import { useMemo, useState } from 'react';
import type { OptionsSummary } from '../lib/types';
import styles from '../styles/OptionsCard.module.css';

type OptionsCardProps = {
  symbol: string;
  summary: OptionsSummary | null;
  loading: boolean;
  error?: string | null;
  onRetry: () => void;
};

export function OptionsCard({ symbol, summary, loading, error, onRetry }: OptionsCardProps) {
  const [expanded, setExpanded] = useState(false);

  const snapshot = useMemo(() => normalizeSummary(summary), [summary]);
  const hasData = snapshot.hasCoreData;

  const togglePanel = () => {
    setExpanded((prev) => !prev);
  };

  return (
    <article className={styles.card}>
      <header className={styles.header}>
        <div>
          <span className={styles.eyebrow}>Market Pulse</span>
          <h3>Options desk read on {symbol}</h3>
        </div>
        <div className={styles.chips}>
          <span className={`${styles.chip} ${snapshot.ivTone}`}>IV30 {snapshot.iv30Text}</span>
          <span className={`${styles.chip} ${snapshot.skewTone}`}>Skew {snapshot.skewText}</span>
          <span className={styles.asOf}>as of {snapshot.asOf}</span>
        </div>
      </header>

      {loading && <p className={styles.loading}>Refreshing options snapshot…</p>}
      {error && <p className={styles.error}>{error}</p>}

      {hasData ? (
        <>
          <ul className={styles.takeaways}>
            {snapshot.takeaways.map((line) => (
              <li key={line}>{line}</li>
            ))}
          </ul>
          <div className={styles.actions}>
            <button type="button" className={styles.primaryButton} onClick={togglePanel}>
              {expanded ? 'Close chain' : 'See chain'}
            </button>
            <button type="button" className={styles.secondaryButton} onClick={onRetry}>
              Refresh
            </button>
          </div>
        </>
      ) : (
        <div className={styles.degraded}>
          <p>{snapshot.takeaways[0]}</p>
          <button type="button" className={styles.secondaryButton} onClick={onRetry}>
            Retry
          </button>
        </div>
      )}

      {expanded && hasData && (
        <div className={styles.panel}>
          <section>
            <h4>Summary</h4>
            <ul>
              {snapshot.takeaways.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </section>
          <section>
            <h4>Evidence</h4>
            <dl className={styles.evidenceGrid}>
              {snapshot.evidence.map((item) => (
                <div key={item.label} className={styles.evidenceItem}>
                  <dt>{item.label}</dt>
                  <dd>{item.value}</dd>
                </div>
              ))}
            </dl>
          </section>
          <section>
            <h4>Data</h4>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th scope="col">Side</th>
                  <th scope="col">Strike</th>
                  <th scope="col">OI Δ</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>Call</td>
                  <td>{snapshot.topCallStrike}</td>
                  <td>{snapshot.topCallChange}</td>
                </tr>
                <tr>
                  <td>Put</td>
                  <td>{snapshot.topPutStrike}</td>
                  <td>{snapshot.topPutChange}</td>
                </tr>
              </tbody>
            </table>
          </section>
        </div>
      )}
    </article>
  );
}

function normalizeSummary(summary: OptionsSummary | null) {
  if (!summary) {
    return {
      iv30Text: '—',
      ivTone: styles.chipNeutral,
      skewText: '—',
      skewTone: styles.chipNeutral,
      asOf: '—',
      takeaways: ['Not enough options data—will retry.'],
      evidence: [],
      hasCoreData: false,
      topCallStrike: '—',
      topCallChange: '—',
      topPutStrike: '—',
      topPutChange: '—',
    };
  }

  const iv30Text = summary.iv30 != null ? `${summary.iv30.toFixed(1)}%` : '—';
  const skewText = summary.skew25d != null ? `${summary.skew25d.toFixed(2)} vols` : '—';

  const ivTone = summary.ivChangePctDoD != null && summary.ivChangePctDoD <= -5
    ? styles.chipPositive
    : summary.ivChangePctDoD != null && summary.ivChangePctDoD >= 5
      ? styles.chipNegative
      : styles.chipNeutral;

  const skewTone = summary.skew25d != null && summary.skew25d >= 3
    ? styles.chipNegative
    : summary.skew25d != null && summary.skew25d <= -3
      ? styles.chipPositive
      : styles.chipNeutral;

  const asOfFormatter = new Intl.DateTimeFormat('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'America/New_York',
  });

  const asOf = summary.asOf ? `${asOfFormatter.format(new Date(summary.asOf))} ET` : '—';
  const topCallStrike = summary.topCallOI ? summary.topCallOI.strike.toFixed(2) : '—';
  const topPutStrike = summary.topPutOI ? summary.topPutOI.strike.toFixed(2) : '—';
  const topCallChange = summary.topCallOI ? formatChange(summary.topCallOI.change) : '—';
  const topPutChange = summary.topPutOI ? formatChange(summary.topPutOI.change) : '—';

  return {
    iv30Text,
    ivTone,
    skewText,
    skewTone,
    asOf,
    takeaways: summary.takeaways.length ? summary.takeaways : ['Vol steady; stay tactical for best entries—if liquidity holds.'],
    evidence: summary.evidence,
    hasCoreData: summary.iv30 != null || summary.skew25d != null,
    topCallStrike,
    topCallChange,
    topPutStrike,
    topPutChange,
  };
}

function formatChange(value: number): string {
  if (value === 0) {
    return 'flat';
  }
  const prefix = value > 0 ? '+' : '';
  return `${prefix}${value}`;
}
