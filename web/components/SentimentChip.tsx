'use client';

import { useState } from 'react';
import type { PcrResponse } from '../lib/types';
import styles from '../styles/SentimentChip.module.css';

type SentimentChipProps = {
  data: PcrResponse | null;
  loading: boolean;
  error?: string | null;
  onRetry: () => void;
};

export function SentimentChip({ data, loading, error, onRetry }: SentimentChipProps) {
  const [open, setOpen] = useState(false);

  const valueText = Number.isFinite(data?.today ?? NaN) ? (data!.today).toFixed(2) : '—';
  const tone = data?.isExtremeHigh ? 'high' : data?.isExtremeLow ? 'low' : 'neutral';

  const toggle = () => setOpen((prev) => !prev);

  return (
    <div className={styles.wrapper}>
      <button
        type="button"
        className={`${styles.chip} ${styles[`chip${tone.charAt(0).toUpperCase()}${tone.slice(1)}`]}`}
        onClick={toggle}
      >
        <span className={styles.label}>PCR</span>
        <span className={styles.value}>{valueText}</span>
      </button>
      {loading && <span className={styles.status}>refreshing…</span>}
      {error && <span className={styles.error}>{error}</span>}

      {open && (
        <div className={styles.panel}>
          <header>
            <h4>Put/Call Ratio</h4>
            <button type="button" onClick={toggle} aria-label="Close PCR panel">
              ✕
            </button>
          </header>
          {data ? (
            <div className={styles.panelBody}>
              <p className={styles.takeaway}>{data.takeaway}</p>
              <dl>
                <div>
                  <dt>MA5</dt>
                  <dd>{data.ma5.toFixed(2)}</dd>
                </div>
                <div>
                  <dt>MA10</dt>
                  <dd>{data.ma10.toFixed(2)}</dd>
                </div>
                <div>
                  <dt>Z10</dt>
                  <dd>{data.z10.toFixed(2)}</dd>
                </div>
              </dl>
              <div className={styles.panelFooter}>
                <span>as of {formatAsOf(data.asOf)}</span>
                <button type="button" onClick={onRetry} className={styles.retry}>
                  Retry
                </button>
              </div>
            </div>
          ) : (
            <div className={styles.panelBody}>
              <p className={styles.takeaway}>No PCR today. We&apos;ll ping the feed and refresh shortly.</p>
              <button type="button" onClick={onRetry} className={styles.retry}>
                Retry
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function formatAsOf(asOf: string): string {
  try {
    const formatter = new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: '2-digit',
      timeZone: 'America/New_York',
    });
    return `${formatter.format(new Date(asOf))} ET`;
  } catch (error) {
    if (process.env.NODE_ENV !== 'production') {
      // eslint-disable-next-line no-console
      console.warn('Failed to format PCR date', error);
    }
    return '—';
  }
}
