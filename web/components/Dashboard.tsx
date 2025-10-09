'use client';

import { useEffect, useState } from 'react';
import { fetchLatestEnsemble } from '../lib/api';
import type { EnsembleResponse } from '../lib/types';
import { Panel } from './Panel';
import { AlertDraftPanel } from './AlertDraftPanel';
import { AuditTrail } from './AuditTrail';
import { HistoryTable } from './HistoryTable';
import { PerformancePanel } from './PerformancePanel';
import styles from '../styles/Dashboard.module.css';

const DEFAULT_SYMBOL = 'QQQ';

export function Dashboard() {
  const [latest, setLatest] = useState<EnsembleResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchLatestEnsemble(DEFAULT_SYMBOL);
        if (!mounted) return;
        setLatest(data);
      } catch (err) {
        if (!mounted) return;
        const status = (err as Error & { status?: number })?.status;
        if (status === 404) {
          setLatest(null);
          setError(null);
        } else {
          setError(err instanceof Error ? err.message : 'Failed to load latest alert');
        }
      } finally {
        if (mounted) setLoading(false);
      }
    };

    void load();
    const interval = setInterval(load, 60_000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  return (
    <div className={styles.dashboard}>
      {error && <div className={styles.banner}>{error}</div>}
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
