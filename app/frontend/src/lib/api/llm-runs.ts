import { isBuildTime, isProduction, request } from './base-client';
import { getMockLLMRuns } from './mocks';
import type { PaginatedLLMRuns } from './types';

export async function getLLMRuns(params?: { task?: string; status?: string; limit?: number; offset?: number }): Promise<PaginatedLLMRuns> {
  try {
    const q = new URLSearchParams();
    if (params?.task) q.set('task', params.task);
    if (params?.status) q.set('status', params.status);
    if (params?.limit) q.set('limit', String(params.limit));
    if (params?.offset) q.set('offset', String(params.offset));
    const query = q.toString();
    return await request<PaginatedLLMRuns>(`/api/llm-runs${query ? '?' + query : ''}`);
  } catch {
    if (isProduction() && !isBuildTime()) throw new Error('API unreachable');
    const items = getMockLLMRuns();
    return { items, total: items.length };
  }
}
