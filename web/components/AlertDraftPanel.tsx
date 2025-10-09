'use client';

import { EnsembleResponse } from '../lib/types';
import styles from '../styles/AlertDraftPanel.module.css';

interface AlertDraftPanelProps {
  latest: EnsembleResponse | null;
  loading?: boolean;
}

export function AlertDraftPanel({ latest, loading }: AlertDraftPanelProps) {
  if (loading) {
    return <div className={styles.loading}>Preparing alert draft...</div>;
  }

  if (!latest || !latest.rth_ticket) {
    return <div className={styles.empty}>Awaiting qualifying RTH options setup.</div>;
  }

  const ticket = latest.rth_ticket as Record<string, unknown>;
  const entryRules = (ticket.entry_rules as string[]) ?? [];
  const stopRules = (ticket.stop_rules as string[]) ?? [];
  const targets = (ticket.targets as string[]) ?? [];
  const notes = ticket.notes as Record<string, unknown> | undefined;

  return (
    <div className={styles.ticketCard}>
      <div className={styles.watermark}>Alert Only – Not an Order</div>
      <header className={styles.header}>
        <div>
          <h3>{ticket.underlying}</h3>
          <p>{ticket.structure} · {ticket.expiry}</p>
        </div>
        <div className={styles.meta}>
          <span>Delta {ticket.delta}</span>
          <span>{notes?.direction as string}</span>
        </div>
      </header>

      <div className={styles.sectionGrid}>
        <section>
          <h4>Entry Rules</h4>
          <ul>
            {entryRules.map((rule) => (
              <li key={rule}>{rule}</li>
            ))}
          </ul>
        </section>
        <section>
          <h4>Stops</h4>
          <ul>
            {stopRules.map((rule) => (
              <li key={rule}>{rule}</li>
            ))}
          </ul>
        </section>
        <section>
          <h4>Targets</h4>
          <ul>
            {targets.map((target) => (
              <li key={target}>{target}</li>
            ))}
          </ul>
        </section>
      </div>

      <footer className={styles.footer}>
        <div>
          <h4>Sizing Formula</h4>
          <p>{ticket.sizing_formula as string}</p>
        </div>
        <div>
          <h4>Context</h4>
          <p>
            IV {notes?.implied_vol?.toString() ?? 'n/a'} · Realized {notes?.realized_vol?.toString() ?? 'n/a'} · Ratio{' '}
            {notes?.vol_ratio?.toString() ?? 'n/a'}
          </p>
        </div>
      </footer>
    </div>
  );
}
