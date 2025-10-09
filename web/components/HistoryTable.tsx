'use client';

import { useEffect, useMemo, useState } from 'react';
import { fetchHistory } from '../lib/api';
import type { AlertRecord } from '../lib/types';
import styles from '../styles/HistoryTable.module.css';

const PAGE_SIZE = 20;

interface HistoryPayload {
  items: AlertRecord[];
  total: number;
}

export function HistoryTable() {
  const [page, setPage] = useState(1);
  const [startDate, setStartDate] = useState<string>('');
  const [endDate, setEndDate] = useState<string>('');
  const [history, setHistory] = useState<HistoryPayload>({ items: [], total: 0 });
  const [startDraft, setStartDraft] = useState<string>('');
  const [endDraft, setEndDraft] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchHistory(page, PAGE_SIZE, startDate || undefined, endDate || undefined);
        if (!mounted) return;
        setHistory({ items: data.items, total: data.total });
      } catch (err) {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : 'Failed to load history');
      } finally {
        if (mounted) setLoading(false);
      }
    };

    void load();
    return () => {
      mounted = false;
    };
  }, [page, startDate, endDate]);

  const totalPages = useMemo(() => Math.max(1, Math.ceil(history.total / PAGE_SIZE)), [history.total]);

  const onExportCsv = () => {
    if (!history.items.length) return;
    const headers = ['Timestamp', 'Symbol', 'Decision', 'Confidence', 'Method', 'Risk', 'Notes'];
    const rows = history.items.map((item) => [
      new Date(item.ts).toISOString(),
      item.symbol,
      item.overall_decision,
      item.confidence.toFixed(2),
      item.method,
      item.risk_pass ? 'pass' : 'veto',
      item.auditor_notes ? JSON.stringify(item.auditor_notes) : '',
    ]);
    const csv = [headers, ...rows].map((line) => line.map((cell) => `"${cell.replace?.(/"/g, '""') ?? cell}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `alerts-history-page-${page}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  useEffect(() => {
    setStartDraft(startDate);
  }, [startDate]);

  useEffect(() => {
    setEndDraft(endDate);
  }, [endDate]);

  const onFilterSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setPage(1);
    setStartDate(startDraft);
    setEndDate(endDraft);
  };

  return (
    <div className={styles.container}>
      <form className={styles.filters} onSubmit={onFilterSubmit}>
        <div className={styles.filterField}>
          <label htmlFor="start">Start</label>
          <input type="date" id="start" name="start" value={startDraft} onChange={(event) => setStartDraft(event.target.value)} />
        </div>
        <div className={styles.filterField}>
          <label htmlFor="end">End</label>
          <input type="date" id="end" name="end" value={endDraft} onChange={(event) => setEndDraft(event.target.value)} />
        </div>
        <div className={styles.controls}>
          <button type="submit">Apply</button>
          <button type="button" onClick={onExportCsv} disabled={!history.items.length}>
            Export CSV
          </button>
        </div>
      </form>

      {error && <div className={styles.error}>{error}</div>}
      {!error && (
        <div className={styles.tableWrapper}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Symbol</th>
                <th>Decision</th>
                <th>Confidence</th>
                <th>Method</th>
                <th>Risk</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={6} className={styles.loading}>
                    Loading...
                  </td>
                </tr>
              )}
              {!loading && history.items.length === 0 && (
                <tr>
                  <td colSpan={6} className={styles.empty}>
                    No alerts found for the selected window.
                  </td>
                </tr>
              )}
              {!loading &&
                history.items.map((item) => (
                  <tr key={item.id}>
                    <td>{new Date(item.ts).toLocaleString()}</td>
                    <td>{item.symbol}</td>
                    <td>{item.overall_decision}</td>
                    <td>{item.confidence.toFixed(2)}</td>
                    <td>{item.method}</td>
                    <td className={item.risk_pass ? styles.riskPass : styles.riskFail}>
                      {item.risk_pass ? 'Pass' : 'Veto'}
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}

      <div className={styles.pagination}>
        <button type="button" disabled={page === 1 || loading} onClick={() => setPage((p) => Math.max(1, p - 1))}>
          Previous
        </button>
        <span>
          Page {page} / {totalPages}
        </span>
        <button type="button" disabled={page >= totalPages || loading} onClick={() => setPage((p) => Math.min(totalPages, p + 1))}>
          Next
        </button>
      </div>
    </div>
  );
}
