import type { AnalyticsData } from '../types/analytics';

const STORAGE_KEY = 'rag_gate_api_key';
const API_BASE = '/api/v1';

function getApiKey(): string | null {
  return localStorage.getItem(STORAGE_KEY);
}

export function setApiKey(key: string): void {
  localStorage.setItem(STORAGE_KEY, key);
}

export function clearApiKey(): void {
  localStorage.removeItem(STORAGE_KEY);
}

export function hasApiKey(): boolean {
  return !!getApiKey();
}

async function fetchWithAuth<T>(path: string): Promise<T> {
  const key = getApiKey();
  if (!key) {
    throw new Error('No API key configured');
  }

  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      Authorization: `Api-Key ${key}`,
      'Content-Type': 'application/json',
    },
  });

  if (response.status === 401 || response.status === 403) {
    clearApiKey();
    throw new Error('Invalid API key');
  }

  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || body.error || `Request failed (${response.status})`);
  }

  return response.json();
}

export async function fetchAnalytics(): Promise<AnalyticsData> {
  return fetchWithAuth<AnalyticsData>('/analytics/');
}

export async function validateApiKey(key: string): Promise<boolean> {
  // Temporarily set the key to test it
  const previous = getApiKey();
  setApiKey(key);
  try {
    await fetchAnalytics();
    return true;
  } catch {
    // Restore previous key on failure
    if (previous) {
      setApiKey(previous);
    } else {
      clearApiKey();
    }
    return false;
  }
}