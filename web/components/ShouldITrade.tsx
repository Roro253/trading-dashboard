'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';

import { fetchShouldITrade } from '../lib/api';
import type { ShouldITradeDecision, ShouldITradeResponse, SignalSnapshot } from '../lib/types';
import { Panel } from './Panel';
import styles from '../styles/ShouldITrade.module.css';

const REFRESH_MS = 45_000;

const DECISION_COLOR: Record<ShouldITradeDecision, string> = {
  YES: '#00ff88',
  CAUTION: '#ffc400',
  NO: '#ff4444',
};

const DECISION_CLASS: Record<ShouldITradeDecision, string> = {
  YES: styles.badgeYES,
  CAUTION: styles.badgeCAUTION,
  NO: styles.badgeNO,
};

const BUCKET_ORDER = [
  'credit_liquidity',
  'vol_term_structure',
  'trend',
  'breadth',
  'dealer_positioning',
  'positioning_sentiment',
  'cross_asset',
  'calendar',
];

function bucketLabel(key: string): string {
  return key.replace(/_/g, ' ');
}

function scoreColor(score: number): string {
  if (score >= 80) return '#00ff88';
  if (score >= 60) return '#ffc400';
  return '#ff4444';
}

function ScoreRing({ score }: { score: number }) {
  const radius = 70;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(100, score));
  const offset = circumference * (1 - clamped / 100);
  return (
    <div className={styles.scoreWrap} aria-label={`Market quality score ${score.toFixed(0)}`}>
      <svg className={styles.scoreSvg} width={180} height={180}>
        <circle cx={90} cy={90} r={radius} className={styles.scoreTrack} strokeWidth={12} />
        <circle
          cx={90}
          cy={90}
          r={radius}
          className={styles.scoreFill}
          strokeWidth={12}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          style={{ stroke: scoreColor(clamped) }}
        />
      </svg>
      <div className={styles.scoreLabel}>
        <div className={styles.scoreValue}>{clamped.toFixed(0)}</div>
        <div className={styles.scoreSub}>Market Quality</div>
      </div>
    </div>
  );
}

function BucketBars({ buckets }: { buckets: Record<string, number> }) {
  return (
    <div className={styles.buckets}>
      {BUCKET_ORDER.filter((b) => b in buckets).map((b) => {
        const value = buckets[b];
        return (
          <div key={b} className={styles.bucketRow}>
            <div className={styles.bucketName}>{bucketLabel(b)}</div>
            <div className={styles.bucketBarOuter}>
              <div className={styles.bucketBarFill} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} />
            </div>
            <div className={styles.bucketValue}>{value.toFixed(0)}</div>
          </div>
        );
      })}
    </div>
  );
}

function SignalsTable({ signals }: { signals: SignalSnapshot[] }) {
  if (signals.length === 0) {
    return <p className={styles.neutral}>No signal snapshots available yet.</p>;
  }
  return (
    <table className={styles.signalTable}>
      <thead>
        <tr>
          <th>Signal</th>
          <th>Bucket</th>
          <th>Value</th>
          <th>Z</th>
          <th>Score</th>
        </tr>
      </thead>
      <tbody>
        {signals.map((s) => {
          const zClass = s.zscore == null ? styles.neutral : s.zscore > 0 ? styles.good : styles.bad;
          return (
            <tr key={s.name}>
              <td>{s.name}</td>
              <td className={styles.neutral}>{bucketLabel(s.bucket)}</td>
              <td>{s.value == null ? '—' : s.value.toFixed(2)}</td>
              <td className={zClass}>{s.zscore == null ? '—' : s.zscore.toFixed(2)}</td>
              <td>{s.bucket_score.toFixed(0)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

export function ShouldITrade() {
  const [data, setData] = useState<ShouldITradeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [lastFetched, setLastFetched] = useState<Date | null>(null);

  const load = useCallback(async () => {
    try {
      const resp = await fetchShouldITrade();
      setData(resp);
      setError(null);
      setLastFetched(new Date());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
    const id = setInterval(() => void load(), REFRESH_MS);
    return () => clearInterval(id);
  }, [load]);

  const agoLabel = useMemo(() => {
    if (!lastFetched) return null;
    const deltaMs = Date.now() - lastFetched.getTime();
    const s = Math.round(deltaMs / 1000);
    return `updated ${s}s ago`;
  }, [lastFetched, data]);

  return (
    <Panel
      title="Should I Be Trading?"
      subtitle="Live regime score with credit, vol term-structure, and breadth kill-switches"
      actions={
        <button onClick={() => void load()} type="button">
          {loading ? 'Refreshing…' : 'Refresh'}
        </button>
      }
    >
      {error && (
        <div className={styles.errorBanner}>
          <strong>Endpoint unavailable:</strong> {error}
        </div>
      )}

      {!data && !error && (
        <div className={styles.wrapper}>
          <div className={styles.hero}>
            <div className={styles.skeleton} style={{ width: 200, height: 60 }} />
            <div className={styles.skeleton} style={{ width: 180, height: 180, borderRadius: '50%' }} />
          </div>
          <div className={styles.details}>
            <div className={styles.skeleton} style={{ height: 140 }} />
            <div className={styles.skeleton} style={{ height: 140 }} />
          </div>
        </div>
      )}

      {data && (
        <>
          <div className={styles.wrapper}>
            <div className={styles.hero}>
              <div
                className={`${styles.badge} ${DECISION_CLASS[data.decision]}`}
                style={{ color: DECISION_COLOR[data.decision] }}
              >
                {data.decision}
              </div>
              <ScoreRing score={data.market_quality_score} />
              {data.reason_codes.length > 0 && (
                <div className={styles.reasonCodes}>{data.reason_codes.join(' · ')}</div>
              )}
            </div>

            <div className={styles.details}>
              {data.triggered_kill_switches.length > 0 && (
                <div className={styles.killBanner}>
                  <h4>Kill-switches triggered</h4>
                  <ul>
                    {data.triggered_kill_switches.map((k) => (
                      <li key={k}>{k.replace(/_/g, ' ')}</li>
                    ))}
                  </ul>
                </div>
              )}
              <BucketBars buckets={data.bucket_scores} />
              <SignalsTable signals={data.signals} />
            </div>
          </div>

          <div className={styles.footer}>
            <div>
              {agoLabel} · composite raw: {data.composite_raw.toFixed(1)}
              {data.market_quality_is_percentile ? ' · percentile-mapped' : ' · raw composite (cold start)'}
              {data.degraded_feeds.length > 0 && ` · degraded: ${data.degraded_feeds.join(', ')}`}
            </div>
            <div>generated at {new Date(data.generated_at).toLocaleTimeString()}</div>
          </div>
        </>
      )}
    </Panel>
  );
}
