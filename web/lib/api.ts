import { EnsembleResponse, HistoryResponse, PerformanceResponse } from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${API_BASE}${path}`;
  const response = await fetch(url, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
    },
    cache: 'no-store',
  });

  if (!response.ok) {
    const message = await response.text();
    const error = new Error(`API request failed (${response.status}): ${message}`);
    (error as Error & { status?: number }).status = response.status;
    throw error;
  }

  return response.json() as Promise<T>;
}

export async function fetchHistory(
  page: number,
  pageSize: number,
  start?: string,
  end?: string,
): Promise<HistoryResponse> {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
  });

  if (start) params.set('start', start);
  if (end) params.set('end', end);

  return apiFetch<HistoryResponse>(`/api/history?${params.toString()}`);
}

export async function fetchPerformance(agentKey?: string, window?: string): Promise<PerformanceResponse> {
  const params = new URLSearchParams();
  if (agentKey) params.set('agent_key', agentKey);
  if (window) params.set('window', window);
  const query = params.toString();
  const path = query ? `/api/performance?${query}` : '/api/performance';
  return apiFetch<PerformanceResponse>(path);
}

export async function fetchLatestEnsemble(symbol: string): Promise<EnsembleResponse> {
  return apiFetch<EnsembleResponse>(`/api/ensemble/${encodeURIComponent(symbol)}`);
}
