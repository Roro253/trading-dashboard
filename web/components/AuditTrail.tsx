'use client';

import { EnsembleResponse } from '../lib/types';
import styles from '../styles/AuditTrail.module.css';

interface AuditTrailProps {
  latest: EnsembleResponse | null;
  loading?: boolean;
}

interface AuditCheck {
  name: string;
  status: 'pass' | 'fail';
  detail: string;
}

export function AuditTrail({ latest, loading }: AuditTrailProps) {
  if (loading) {
    return <div className={styles.loading}>Loading audit trail...</div>;
  }

  if (!latest) {
    return <div className={styles.empty}>No alert selected yet.</div>;
  }

  const notes = (latest.portfolio_snapshot?.overall as Record<string, unknown>)?.['auditor_notes'] as
    | Record<string, unknown>
    | undefined;
  const auditorNotes = notes || (latest.portfolio_snapshot?.auditor_notes as Record<string, unknown> | undefined);
  const structuredChecks = Array.isArray(
    (latest.portfolio_snapshot?.auditor_notes as { checks?: AuditCheck[] } | undefined)?.checks,
  )
    ? ((latest.portfolio_snapshot?.auditor_notes as { checks?: AuditCheck[] })?.checks ?? [])
    : [];
  const risk = latest.portfolio_snapshot?.risk as { reasons?: string[] } | undefined;
  const market = latest.portfolio_snapshot?.market as Record<string, unknown> | undefined;
  const previousClose = market?.previous_close as Record<string, unknown> | undefined;
  const optionsSnapshot = market?.options_snapshot as Record<string, unknown> | undefined;

  const failureModes = Array.isArray(auditorNotes?.failure_modes) ? (auditorNotes?.failure_modes as string[]) : [];

  return (
    <div className={styles.container}>
      <div className={styles.summaryRow}>
        <div>
          <h3>Decision</h3>
          <p className={styles.decision}>{latest.overall_decision}</p>
        </div>
        <div>
          <h3>Confidence</h3>
          <p>{(latest.confidence * 100).toFixed(1)}%</p>
        </div>
        <div>
          <h3>Method</h3>
          <p>{latest.method}</p>
        </div>
      </div>

      <div className={styles.section}>
        <h4>Auditor Notes</h4>
        {auditorNotes ? (
          <ul>
            {structuredChecks.length > 0 && (
              <li>
                <span>Summary Checks:</span>
                <ul className={styles.innerList}>
                  {structuredChecks.map((check) => (
                    <li key={check.name}>
                      <strong>{check.name}</strong> — {check.status.toUpperCase()} · {check.detail}
                    </li>
                  ))}
                </ul>
              </li>
            )}
            {failureModes.length > 0 && (
              <li>
                <span>Failure Modes:</span>
                <ul className={styles.innerList}>
                  {failureModes.map((mode) => (
                    <li key={mode}>{mode}</li>
                  ))}
                </ul>
              </li>
            )}
            {Object.entries(auditorNotes)
              .filter(([key]) => key !== 'failure_modes' && key !== 'checks')
              .map(([key, value]) => (
                <li key={key}>
                  <span>{key}:</span> {JSON.stringify(value)}
                </li>
              ))}
          </ul>
        ) : (
          <p className={styles.muted}>No auditor notes recorded.</p>
        )}
      </div>

      <div className={styles.section}>
        <h4>Risk Reasons</h4>
        {risk?.reasons && risk.reasons.length > 0 ? (
          <ul className={styles.innerList}>
            {risk.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
        ) : (
          <p className={styles.muted}>No risk veto triggers.</p>
        )}
      </div>

      <div className={styles.section}>
        <h4>Evidence Snapshot</h4>
        <ul className={styles.innerList}>
          {previousClose && (
            <li>
              Previous Close: {(previousClose.close as number | undefined)?.toFixed?.(2) ?? 'n/a'} · Volume{' '}
              {previousClose.volume ?? 'n/a'}
            </li>
          )}
          {optionsSnapshot && (
            <li>
              Options: IV {optionsSnapshot.implied_volatility ?? 'n/a'} · Rank {optionsSnapshot.implied_vol_rank ?? 'n/a'} ·
              Skew {optionsSnapshot.skew_proxy ?? 'n/a'}
            </li>
          )}
          {!previousClose && !optionsSnapshot && <li>No market evidence captured.</li>}
        </ul>
      </div>
    </div>
  );
}
