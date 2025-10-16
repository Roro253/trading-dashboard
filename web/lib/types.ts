export type Decision = 'BUY' | 'SELL' | 'HOLD' | 'NO_TRADE';

export interface AlertRecord {
  id: string;
  symbol: string;
  ts: string;
  overall_decision: Decision;
  confidence: number;
  method: string;
  risk_pass: boolean;
  portfolio_snapshot: Record<string, unknown>;
  auditor_notes?: Record<string, unknown> | null;
  rth_ticket?: Record<string, unknown> | null;
}

export interface HistoryResponse {
  page: number;
  page_size: number;
  total: number;
  items: AlertRecord[];
}

export interface MetricsSnapshot {
  agent_key: string;
  window: '7d' | '30d';
  hit_rate: number;
  avg_R: number;
  sharpe: number;
  profit_factor: number;
  drawdown: number;
  samples: number;
  calibration_bins: Record<string, number>;
  as_of: string;
}

export interface PerformanceResponse {
  metrics: MetricsSnapshot[];
}

export interface EnsembleResponse {
  symbol: string;
  overall_decision: Decision;
  confidence: number;
  method: string;
  portfolio_snapshot: Record<string, unknown>;
  risk_pass: boolean;
  rth_ticket?: Record<string, unknown> | null;
}

export type MarketStatus = 'open' | 'closed' | 'pre' | 'post' | 'unknown';

export interface PriceResponse {
  symbol: string;
  last: number;
  prevClose: number;
  changePct: number;
  marketStatus: MarketStatus;
  asOf: string;
  source: 'polygon';
  stale: boolean;
}

export interface OptionsSummary {
  symbol: string;
  iv30: number | null;
  ivChangePctDoD: number | null;
  skew25d: number | null;
  topCallOI: { strike: number; change: number } | null;
  topPutOI: { strike: number; change: number } | null;
  asOf: string;
  takeaways: string[];
  evidence: { label: string; value: string }[];
  source: 'polygon';
}

export interface PcrResponse {
  today: number;
  ma5: number;
  ma10: number;
  z10: number;
  isExtremeHigh: boolean;
  isExtremeLow: boolean;
  takeaway: string;
  asOf: string;
  source: 'cboe';
}
