'use client';

import { useEffect, useMemo, useState } from 'react';
import {
  ColumnDef,
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from '@tanstack/react-table';
import { fetchPerformance } from '../lib/api';
import type { MetricsSnapshot } from '../lib/types';
import { SparkBar } from './charts/SparkBar';
import styles from '../styles/PerformancePanel.module.css';

const columnHelper = createColumnHelper<MetricsSnapshot>();

const columns: ColumnDef<MetricsSnapshot, any>[] = [
  columnHelper.accessor('agent_key', {
    header: 'Agent',
    cell: (info) => info.getValue(),
  }),
  columnHelper.accessor('window', {
    header: 'Window',
    cell: (info) => info.getValue(),
  }),
  columnHelper.accessor('hit_rate', {
    header: 'Hit Rate',
    cell: (info) => `${(info.getValue() * 100).toFixed(1)}%`,
  }),
  columnHelper.accessor('avg_R', {
    header: 'Expectancy (R)',
    cell: (info) => info.getValue().toFixed(3),
  }),
  columnHelper.accessor('sharpe', {
    header: 'Sharpe',
    cell: (info) => info.getValue().toFixed(2),
  }),
  columnHelper.accessor('profit_factor', {
    header: 'Profit Factor',
    cell: (info) => info.getValue().toFixed(2),
  }),
  columnHelper.accessor('drawdown', {
    header: 'Drawdown',
    cell: (info) => `${(info.getValue() * 100).toFixed(1)}%`,
  }),
  columnHelper.accessor('samples', {
    header: 'Samples',
  }),
];

export function PerformancePanel() {
  const [metrics, setMetrics] = useState<MetricsSnapshot[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let mounted = true;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await fetchPerformance();
        if (!mounted) return;
        setMetrics(data.metrics);
      } catch (err) {
        if (!mounted) return;
        setError(err instanceof Error ? err.message : 'Failed to load performance');
      } finally {
        if (mounted) setLoading(false);
      }
    };

    void load();
    return () => {
      mounted = false;
    };
  }, []);

  const table = useReactTable({
    data: metrics,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  const chartData = useMemo(() => {
    const grouped = new Map<string, MetricsSnapshot[]>();
    metrics.forEach((metric) => {
      const list = grouped.get(metric.agent_key) ?? [];
      list.push(metric);
      grouped.set(metric.agent_key, list);
    });

    return Array.from(grouped.entries()).map(([agent, values]) => ({
      agent,
      hit: values.map((value) => ({ label: value.window.toUpperCase(), value: value.hit_rate })),
      expectancy: values.map((value) => ({ label: value.window.toUpperCase(), value: value.avg_R })),
    }));
  }, [metrics]);

  return (
    <div className={styles.container}>
      {error && <div className={styles.error}>{error}</div>}
      {loading && !error && <div className={styles.loading}>Loading performance...</div>}

      {!loading && !error && (
        <div className={styles.charts}>
          {chartData.map((entry) => (
            <div key={entry.agent} className={styles.chartBlock}>
              <h3>{entry.agent}</h3>
              <div className={styles.chartGroup}>
                <div>
                  <h4>Hit Rate</h4>
                  <SparkBar data={entry.hit} />
                </div>
                <div>
                  <h4>Expectancy</h4>
                  <SparkBar
                    data={entry.expectancy}
                    max={Math.max(...entry.expectancy.map((d) => d.value), 0.01)}
                    format={(value) => value.toFixed(3)}
                  />
                </div>
              </div>
            </div>
          ))}
          {chartData.length === 0 && <div className={styles.empty}>No performance metrics available yet.</div>}
        </div>
      )}

      <div className={styles.tableWrapper}>
        <table>
          <thead>
            {table.getHeaderGroups().map((headerGroup) => (
              <tr key={headerGroup.id}>
                {headerGroup.headers.map((header) => (
                  <th key={header.id}>{flexRender(header.column.columnDef.header, header.getContext())}</th>
                ))}
              </tr>
            ))}
          </thead>
          <tbody>
            {table.getRowModel().rows.map((row) => (
              <tr key={row.id}>
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>
                ))}
              </tr>
            ))}
            {!metrics.length && !loading && (
              <tr>
                <td colSpan={columns.length} className={styles.empty}>
                  No metrics calculated yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
