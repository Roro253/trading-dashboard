import styles from '../../styles/SparkBar.module.css';

interface SparkBarProps {
  data: Array<{ label: string; value: number }>;
  max?: number;
  format?: (value: number) => string;
}

export function SparkBar({ data, max, format = (value) => `${(value * 100).toFixed(1)}%` }: SparkBarProps) {
  if (!data.length) {
    return <div className={styles.empty}>No data</div>;
  }

  const highest = max ?? Math.max(...data.map((d) => d.value), 0.001);

  return (
    <div className={styles.wrapper}>
      {data.map((entry) => {
        const height = Math.max(6, (entry.value / highest) * 100);
        return (
          <div key={entry.label} className={styles.bar}>
            <div className={styles.barFill} style={{ height: `${height}%` }}>
              <span>{format(entry.value)}</span>
            </div>
            <p>{entry.label}</p>
          </div>
        );
      })}
    </div>
  );
}
