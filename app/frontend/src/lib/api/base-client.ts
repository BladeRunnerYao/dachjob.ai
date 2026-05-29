import type { BackgroundTask, BackgroundTaskListResponse, VersionResponse } from './types';

export function getApiBase() {
  if (typeof window === 'undefined') {
    return process.env.INTERNAL_API_BASE_URL
      || process.env.NEXT_PUBLIC_API_BASE_URL
      || 'http://localhost:8000';
  }
  // In production (cloud deployments), NEXT_PUBLIC_API_BASE_URL should be
  // empty/relative so the frontend calls the API on the same origin.
  // The empty-string fallback to localhost:8000 only applies in local dev.
  return process.env.NEXT_PUBLIC_API_BASE_URL && process.env.NEXT_PUBLIC_API_BASE_URL !== ''
    ? process.env.NEXT_PUBLIC_API_BASE_URL
    : (isProduction() ? '' : 'http://localhost:8000');
}

export function isProduction(): boolean {
  return process.env.NODE_ENV === 'production';
}

export function isBuildTime(): boolean {
  return typeof window === 'undefined' && process.env.NEXT_PHASE !== undefined;
}

function getAuthHeaders(): Record<string, string> {
  if (typeof window === 'undefined') return {};
  const token = localStorage.getItem('auth_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function normalizeFetchError(error: unknown): Error {
  if (error instanceof DOMException && error.name === 'AbortError') {
    return error;
  }
  if (error instanceof TypeError) {
    const message = error.message || '';
    if (/load failed|failed to fetch|networkerror|network request failed/i.test(message)) {
      return new Error('Unable to reach the API. Check NEXT_PUBLIC_API_BASE_URL and CORS_ORIGINS for this cloud deployment.');
    }
  }
  return error instanceof Error ? error : new Error('API unreachable');
}

export async function request<T>(path: string, options?: RequestInit & { timeoutMs?: number }): Promise<T> {
  const { timeoutMs, ...fetchOptions } = options || {};
  const url = `${getApiBase()}${path}`;
  const controller = timeoutMs ? new AbortController() : undefined;
  const timer = controller ? setTimeout(() => controller.abort(), timeoutMs) : undefined;

  try {
    const res = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
        ...fetchOptions.headers,
      } as Record<string, string>,
      cache: 'no-store',
      signal: controller?.signal,
      ...fetchOptions,
    });
    if (timer) clearTimeout(timer);
    if (res.status === 401 && typeof window !== 'undefined') {
      localStorage.removeItem('auth_token');
      window.location.href = '/login';
      throw new Error('Unauthorized');
    }

    const isBackgroundTask = res.status === 202;
    if (isBackgroundTask) {
      return res.json() as T;
    }

    if (!res.ok) {
      let message = `API error: ${res.status}`;
      try {
        const body = await res.json();
        if (body?.error?.message) {
          message = body.error.message;
        } else if (body?.detail) {
          message = body.detail;
        }
      } catch {
        try {
          const text = await res.text();
          if (text) message = text.slice(0, 512);
        } catch {}
      }
      throw new Error(message);
    }
    return res.json();
  } catch (e) {
    if (timer) clearTimeout(timer);
    if (e instanceof DOMException && e.name === 'AbortError') {
      throw new Error(`Request timed out after ${Math.round(timeoutMs! / 1000)}s`);
    }
    throw normalizeFetchError(e);
  }
}

export async function requestBlob(path: string): Promise<Blob> {
  const url = `${getApiBase()}${path}`;
  let res: Response;
  try {
    res = await fetch(url, {
      headers: { ...getAuthHeaders() } as Record<string, string>,
      cache: 'no-store',
    });
  } catch (e) {
    throw normalizeFetchError(e);
  }
  if (res.status === 401 && typeof window !== 'undefined') {
    localStorage.removeItem('auth_token');
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }
  if (!res.ok) {
    let message = `Failed to fetch resume artifact: ${res.status}`;
    try {
      const body = await res.json();
      if (body?.error?.message) {
        message = body.error.message;
      } else if (body?.detail) {
        message = body.detail;
      }
    } catch {
      try {
        const text = await res.text();
        if (text) message = text.slice(0, 512);
      } catch {}
    }
    throw new Error(message);
  }
  return res.blob();
}

export function isBackgroundTaskResponse(data: unknown): data is BackgroundTask {
  return (
    typeof data === 'object' &&
    data !== null &&
    'kind' in data &&
    'status' in data &&
    'id' in data
  );
}

export function checkTaskResult(task: BackgroundTask): void {
  if (task.status === 'failed') {
    const msg = task.error && typeof task.error === 'object'
      ? (task.error as Record<string, unknown>).message || 'Task failed'
      : 'Task failed';
    throw new Error(String(msg));
  }
  if (task.status === 'cancelled') {
    throw new Error('Task was cancelled');
  }
}

export async function pollTask(taskId: string, onUpdate?: (task: BackgroundTask) => void): Promise<BackgroundTask> {
  const terminal = new Set(['succeeded', 'failed', 'cancelled']);
  while (true) {
    const task = await request<BackgroundTask>(`/api/tasks/${taskId}`);
    if (onUpdate) onUpdate(task);
    if (terminal.has(task.status)) return task;
    await new Promise((r) => setTimeout(r, 2000));
  }
}

export async function fetchTask(taskId: string): Promise<BackgroundTask> {
  return request<BackgroundTask>(`/api/tasks/${taskId}`);
}

export async function listTasks(params?: { status?: string; kind?: string; limit?: number; offset?: number }): Promise<BackgroundTaskListResponse> {
  const q = new URLSearchParams();
  if (params?.status) q.set('status', params.status);
  if (params?.kind) q.set('kind', params.kind);
  if (params?.limit) q.set('limit', String(params.limit));
  if (params?.offset) q.set('offset', String(params.offset));
  const query = q.toString();
  return request<BackgroundTaskListResponse>(`/api/tasks${query ? '?' + query : ''}`);
}

export async function initWorkerMode(): Promise<boolean> {
  try {
    const version = await request<VersionResponse>('/api/version');
    return version.worker_enabled;
  } catch {
    return false;
  }
}
