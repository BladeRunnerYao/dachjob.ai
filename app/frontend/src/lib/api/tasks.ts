import { request } from './base-client';
import type { BackgroundTask, BackgroundTaskListResponse, VersionResponse } from './types';

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
