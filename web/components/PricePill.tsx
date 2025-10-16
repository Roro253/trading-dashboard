'use client';

import { useEffect, useMemo, useRef, useState } from 'react';
import type { PriceResponse } from '../lib/types';
import styles from '../styles/PricePill.module.css';

type FlashDirection = 'up' | 'down' | null;

type PricePillProps = {
  symbol: string;
  price: PriceResponse | null;
  loading: boolean;
  error?: string | null;
  onRetry: () => void;
};

export function PricePill({ symbol, price, loading, error, onRetry }: PricePillProps) {
  const [flash, setFlash] = useState<FlashDirection>(null);
  const timeoutRef = useRef<number | null>(null);
  const previous = useRef<PriceResponse | null>(null);

  useEffect(() => {
    previous.current = null;
  }, [symbol]);

  useEffect(() => {
    if (!price) {
      return;
    }

    const prev = previous.current;
    if (timeoutRef.current) {
      window.clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }

    if (prev) {
      if (price.last > prev.last) {
        setFlash('up');
      } else if (price.last < prev.last) {
        setFlash('down');
      } else if (price.changePct !== prev.changePct) {
        setFlash(price.changePct > prev.changePct ? 'up' : 'down');
      } else {
        setFlash(null);
      }

      timeoutRef.current = window.setTimeout(() => {
        setFlash(null);
        timeoutRef.current = null;
      }, 350);
    }

    previous.current = price;

    return () => {
      if (timeoutRef.current) {
        window.clearTimeout(timeoutRef.current);
        timeoutRef.current = null;
      }
    };
  }, [price]);

  const formatted = useMemo(() => formatPricePayload(price), [price]);
  const changeTone = formatted.changePctValue > 0 ? 'up' : formatted.changePctValue < 0 ? 'down' : 'flat';
  const statusKey = (price?.marketStatus ?? 'unknown').toLowerCase() as 'open' | 'closed' | 'pre' | 'post' | 'unknown';

  return (
    <div
      className={[
        styles.shell,
        flash ? styles[`flash${flash === 'up' ? 'Up' : 'Down'}`] : '',
        price?.stale ? styles.stale : '',
      ].join(' ')}
    >
      <div className={styles.headerRow}>
        <span className={styles.symbol}>{symbol}</span>
        <span className={`${styles.marketStatus} ${styles[`status${statusKey.charAt(0).toUpperCase()}${statusKey.slice(1)}`]}`}>
          {(price?.marketStatus ?? 'unknown').toUpperCase()}
        </span>
      </div>

      <div className={styles.priceRow}>
        <span className={styles.last}>{formatted.last}</span>
        <span className={`${styles.change} ${styles[`change${changeTone.charAt(0).toUpperCase()}${changeTone.slice(1)}`]}`}>
          {formatted.changePct}
        </span>
      </div>

      <div className={styles.metaRow}>
        <span className={styles.asOf}>as of {formatted.asOf}</span>
        {price?.stale && (
          <span className={styles.degraded}>
            Degraded • using prev close
            <button type="button" onClick={onRetry} className={styles.retryButton} aria-label="Retry price fetch">
              ↻
            </button>
          </span>
        )}
      </div>

      {loading && <span className={styles.loading}>Refreshing…</span>}
      {error && <span className={styles.error}>{error}</span>}
    </div>
  );
}

function formatPricePayload(price: PriceResponse | null) {
  if (!price) {
    return {
      last: '—',
      changePct: '—% ',
      changePctValue: 0,
      asOf: '—',
    };
  }

  const last = Number.isFinite(price.last) ? `$${price.last.toFixed(2)}` : '—';
  const pctValue = Number.isFinite(price.changePct) ? price.changePct * 100 : NaN;
  const changePct = Number.isFinite(pctValue)
    ? `${pctValue >= 0 ? '+' : ''}${pctValue.toFixed(2)}%`
    : '—';
  const asOf = formatAsOf(price.asOf);

  return {
    last,
    changePct,
    changePctValue: Number.isFinite(pctValue) ? pctValue : 0,
    asOf,
  };
}

function formatAsOf(asOfIso: string): string {
  try {
    const date = new Date(asOfIso);
    if (Number.isNaN(date.getTime())) {
      return '—';
    }
    const formatter = new Intl.DateTimeFormat('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      timeZone: 'America/New_York',
    });
    return `${formatter.format(date)} ET`;
  } catch (error) {
    if (process.env.NODE_ENV !== 'production') {
      // eslint-disable-next-line no-console
      console.warn('failed to format asOf', error);
    }
    return '—';
  }
}
